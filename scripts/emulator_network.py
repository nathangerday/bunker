#!/usr/bin/env python3
"""Block the game's external IPv4/IPv6 traffic on an explicitly selected rooted emulator.

Requires adb and root in the emulator, not administrator rights on the PC.
Only the installed game's UID is affected. Loopback remains available.
Rules are runtime state: reapply after an emulator reboot or app reinstall.
"""
import argparse
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

PACKAGE = "com.square_enix.android_googleplay.nierspww"
ACTIVITY = PACKAGE + "/org.veritr1x.bunker.MainActivity"
FAMILIES = (("iptables", "127.0.0.0/8"), ("ip6tables", "::1/128"))


class Device:
    def __init__(self, adb, serial):
        self.adb, self.serial, self.su = adb, serial, False

    def shell(self, args, *, root=False, check=True):
        command = shlex.join([str(arg) for arg in args])
        if root and self.su:
            command = "su -c " + shlex.quote(command)
        result = subprocess.run([self.adb, "-s", self.serial, "shell", command],
                                capture_output=True, text=True, timeout=20)
        if check and result.returncode:
            raise RuntimeError("Device command failed: " + shlex.join(args) + "\n" + result.stderr.strip() + result.stdout.strip())
        return result

    def require_root(self):
        if self.shell(["id", "-u"]).stdout.strip() == "0":
            return
        self.su = True
        if self.shell(["id", "-u"], root=True, check=False).stdout.strip() != "0":
            raise RuntimeError("This helper needs root enabled in the emulator. No firewall rules were installed.")

    def uid(self):
        output = self.shell(["cmd", "package", "list", "packages", "--user", "0", "-U", PACKAGE]).stdout
        match = re.search(r"^package:" + re.escape(PACKAGE) + r" uid:(\d+)\s*$", output, re.MULTILINE)
        if not match:
            raise RuntimeError("Install the Bunker APK in emulator user 0 first.")
        return validate_uid(int(match.group(1)))


def validate_uid(uid):
    if not isinstance(uid, int) or isinstance(uid, bool) or not 10000 <= uid <= 9999999:
        raise ValueError("Refusing to change firewall rules for a system or invalid UID")
    return uid


def chain(uid):
    return "BUNKER_LOCAL_" + str(validate_uid(uid))


def rule_args(uid):
    return ["OUTPUT", "-m", "owner", "--uid-owner", str(validate_uid(uid)), "-j", chain(uid)]


def table(device, family, args, check=True):
    return device.shell([family, "-w", "5", *args], root=True, check=check)


def block(device, uid):
    """Stop the game before editing either family; a failure never launches it."""
    validate_uid(uid)
    device.shell(["am", "force-stop", PACKAGE])
    name = chain(uid)
    for family, loopback in FAMILIES:
        if table(device, family, ["-S", name], check=False).returncode:
            table(device, family, ["-N", name])
        # This dedicated chain belongs only to this helper and game UID.
        table(device, family, ["-F", name])
        table(device, family, ["-A", name, "-d", loopback, "-j", "RETURN"])
        table(device, family, ["-A", name, "-j", "REJECT"])
        # Put the jump ahead of Android's established-connection allow rules.
        remove_jumps(device, family, uid)
        table(device, family, ["-I", "OUTPUT", "1", *rule_args(uid)[1:]])
    result = status(device, uid)
    if not result["protected"]:
        raise RuntimeError("Could not verify both firewall families. The game remains stopped; inspect status or remove the rules.")
    return result


def remove_jumps(device, family, uid):
    for _ in range(32):
        if table(device, family, ["-C", *rule_args(uid)], check=False).returncode:
            return
        table(device, family, ["-D", *rule_args(uid)])
    raise RuntimeError("Unexpected duplicate firewall rules; refusing an unbounded cleanup")


def remove(device, uid):
    validate_uid(uid)
    for family, _ in FAMILIES:
        remove_jumps(device, family, uid)
        if not table(device, family, ["-S", chain(uid)], check=False).returncode:
            table(device, family, ["-F", chain(uid)])
            table(device, family, ["-X", chain(uid)])


def status(device, uid):
    name = chain(uid)
    families = {}
    for family, loopback in FAMILIES:
        policy = table(device, family, ["-S", name], check=False)
        output = table(device, family, ["-S", "OUTPUT"], check=False)
        rules = [shlex.split(line) for line in policy.stdout.splitlines() if line.startswith("-A ")]
        output_rules = [shlex.split(line) for line in output.stdout.splitlines() if line.startswith("-A ")]
        # iptables canonicalizes ::1/128 to ::1; normalize only that spelling.
        allow = ["-A", name, "-d", loopback, "-j", "RETURN"]
        if rules and loopback == "::1/128" and rules[0] == ["-A", name, "-d", "::1", "-j", "RETURN"]:
            rules[0] = allow
        deny = ["-A", name, "-j", "REJECT"]
        reject_suffix = ["--reject-with", "icmp-port-unreachable" if family == "iptables" else "icmp6-port-unreachable"]
        families[family] = bool(not policy.returncode and not output.returncode and len(rules) == 2
                                and rules[0] == allow and rules[1] in (deny, deny + reject_suffix)
                                and output_rules and output_rules[0] == ["-A", *rule_args(uid)])
    return {"package": PACKAGE, "uid": uid, "protected": all(families.values()), "families": families}


def run(device, uid, action):
    if action == "remove":
        remove(device, uid)
        return {"package": PACKAGE, "uid": uid, "removed": True}
    if action == "status":
        return status(device, uid)
    result = block(device, uid)
    if action == "run":
        device.shell(["am", "start", "-n", ACTIVITY])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["block", "run", "status", "remove"])
    parser.add_argument("--serial", required=True, help="Explicit adb emulator serial; obtain with adb devices")
    parser.add_argument("--adb", default="adb", help="adb executable or absolute path")
    args = parser.parse_args()
    adb = shutil.which(args.adb)
    if not adb:
        parser.error("adb was not found")
    device = Device(str(Path(adb).resolve()), args.serial)
    try:
        device.require_root()
        result = run(device, device.uid(), args.action)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, str(error) + "\nProtection was not established. Keep the emulator offline until this is resolved.\n")
    print(json.dumps(result, indent=2))
    if args.action == "status" and not result["protected"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
