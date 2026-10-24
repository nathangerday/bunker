import subprocess
import unittest

import emulator_network as network


class FakeDevice:
    def __init__(self, fail_ipv6=False):
        self.calls, self.chains, self.jumps = [], {}, {}
        self.fail_ipv6 = fail_ipv6

    def shell(self, args, root=False, check=True):
        self.calls.append(args)
        if args[0] not in ("iptables", "ip6tables"):
            return subprocess.CompletedProcess(args, 0, "", "")
        family, args = args[0], args[3:]
        if self.fail_ipv6 and family == "ip6tables":
            if check:
                raise RuntimeError("IPv6 unavailable")
            return subprocess.CompletedProcess(args, 1, "", "error")
        op, name = args[:2]
        key = (family, name)
        code, output = 0, ""
        if op == "-S":
            if name == "OUTPUT":
                output = "\n".join("-A " + " ".join(rule) for rule in self.jumps.get(family, []))
            elif key not in self.chains:
                code = 1
            else:
                output = "\n".join("-A " + name + " " + " ".join(rule) for rule in self.chains[key])
        elif op == "-N":
            self.chains[key] = []
        elif op == "-F":
            self.chains[key] = []
        elif op == "-A":
            self.chains[key].append(args[2:])
        elif op == "-C":
            code = 0 if args[1:] in self.jumps.get(family, []) else 1
        elif op == "-D":
            self.jumps[family].remove(args[1:])
        elif op == "-I":
            self.jumps.setdefault(family, []).insert(0, [name, *args[3:]])
        elif op == "-X":
            del self.chains[key]
        return subprocess.CompletedProcess(args, code, output, "")


class FirewallTests(unittest.TestCase):
    def test_both_families_block_external_destinations_keep_localhost(self):
        device = FakeDevice()
        result = network.run(device, 10123, "run")
        self.assertTrue(result["protected"])
        self.assertEqual(device.calls[0], ["am", "force-stop", network.PACKAGE])
        self.assertEqual(device.calls[-1], ["am", "start", "-n", network.ACTIVITY])
        for family, loopback in network.FAMILIES:
            rules = device.chains[(family, network.chain(10123))]
            self.assertEqual(rules, [["-d", loopback, "-j", "RETURN"], ["-j", "REJECT"]])

    def test_rerunning_is_idempotent_and_removal_preserves_other_rules(self):
        device = FakeDevice()
        device.jumps = {"iptables": [["OUTPUT", "-j", "unrelated"]]}
        network.run(device, 10123, "block")
        network.run(device, 10123, "block")
        self.assertEqual(len(device.jumps["iptables"]), 2)
        self.assertTrue(network.status(device, 10123)["protected"])
        network.remove(device, 10123)
        self.assertEqual(device.jumps["iptables"], [["OUTPUT", "-j", "unrelated"]])
        self.assertFalse(network.status(device, 10123)["protected"])

    def test_ipv6_failure_never_starts_game_or_claims_protection(self):
        device = FakeDevice(fail_ipv6=True)
        with self.assertRaisesRegex(RuntimeError, "IPv6"):
            network.run(device, 10123, "run")
        self.assertFalse(any(args[:2] == ["am", "start"] for args in device.calls))
        self.assertFalse(network.status(device, 10123)["protected"])

    def test_earlier_bypass_rule_fails_verification(self):
        device = FakeDevice()
        network.block(device, 10123)
        device.jumps["ip6tables"].insert(0, ["OUTPUT", "-j", "ACCEPT"])
        self.assertFalse(network.status(device, 10123)["protected"])

    def test_system_uids_are_refused_before_device_commands(self):
        for uid in (0, 1000, -1, True, "10123"):
            device = FakeDevice()
            with self.assertRaises(ValueError):
                network.block(device, uid)
            self.assertEqual(device.calls, [])


if __name__ == "__main__":
    unittest.main()
