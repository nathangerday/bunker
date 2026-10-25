// Display-only replacement for ShopUtility.GetPlatformPriceString in ARM64 3.7.1.
// Leaves the Decimal price, local rewards and transaction logic unchanged.
#include <android/log.h>
#include <dlfcn.h>
#include <jni.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

typedef struct { uint32_t flags, high; uint64_t low; } Decimal;
_Static_assert(sizeof(Decimal) == 16, "IL2CPP Decimal ABI");
static JavaVM *vm;
static jclass formatter;
static jmethodID format_decimal;
static void *(*new_string)(const uint16_t *, int32_t);
static int installed;

static void *format_price(Decimal price, void *platform_text, void *method) {
    (void)method;
    if (platform_text && *(int32_t *)((uint8_t *)platform_text + 16) > 0) return platform_text;
    JNIEnv *env = NULL;
    int attached = 0;
    if ((*vm)->GetEnv(vm, (void **)&env, JNI_VERSION_1_6) != JNI_OK) {
        if ((*vm)->AttachCurrentThread(vm, &env, NULL) != JNI_OK) return NULL;
        attached = 1;
    }
    jstring text = (jstring)(*env)->CallStaticObjectMethod(env, formatter, format_decimal,
            (jint)price.flags, (jint)price.high, (jlong)price.low);
    void *result = NULL;
    if (!(*env)->ExceptionCheck(env) && text) {
        jsize length = (*env)->GetStringLength(env, text);
        const jchar *chars = (*env)->GetStringChars(env, text, NULL);
        if (chars) {
            result = new_string(chars, length);
            (*env)->ReleaseStringChars(env, text, chars);
        }
    }
    if ((*env)->ExceptionCheck(env)) {
        (*env)->ExceptionClear(env);
        __android_log_print(ANDROID_LOG_WARN, "Bunker", "Offline price formatting failed");
    }
    if (text) (*env)->DeleteLocalRef(env, text);
    if (attached) (*vm)->DetachCurrentThread(vm);
    if (!result) {
        const uint16_t unavailable[] = {0x2014};
        result = new_string(unavailable, 1);
    }
    return result;
}

JNIEXPORT jboolean JNICALL Java_org_veritr1x_bunker_ShopPrices_installNative(JNIEnv *env, jclass cls) {
    if (installed) return JNI_TRUE;
    void *library = dlopen("libil2cpp.so", RTLD_NOW);
    void *init = library ? dlsym(library, "il2cpp_init") : NULL;
    Dl_info info;
    if (!init || !dladdr(init, &info)) return JNI_FALSE;
    new_string = (void *(*)(const uint16_t *, int32_t))dlsym(library, "il2cpp_string_new_utf16");
    if (!new_string) return JNI_FALSE;
    uint32_t *at = (uint32_t *)((uint8_t *)info.dli_fbase + 0x2869728);
    const uint32_t expected[] = {0xd10143ff, 0xf9000bf7, 0xa90257f6, 0xa9034ff4};
    if (memcmp(at, expected, sizeof(expected))) return JNI_FALSE;
    if ((*env)->GetJavaVM(env, &vm) != JNI_OK) return JNI_FALSE;
    format_decimal = (*env)->GetStaticMethodID(env, cls, "formatDecimal", "(IIJ)Ljava/lang/String;");
    if (!format_decimal) return JNI_FALSE;
    formatter = (*env)->NewGlobalRef(env, cls);
    if (!formatter) return JNI_FALSE;
    size_t page = (size_t)sysconf(_SC_PAGESIZE);
    uintptr_t begin = (uintptr_t)at & ~(page - 1);
    size_t span = (((uintptr_t)at + 16 + page - 1) & ~(page - 1)) - begin;
    if (mprotect((void *)begin, span, PROT_READ | PROT_WRITE | PROT_EXEC)) {
        (*env)->DeleteGlobalRef(env, formatter);
        return JNI_FALSE;
    }
    at[0] = 0x58000050; // ldr x16, #8
    at[1] = 0xd61f0200; // br x16
    uintptr_t target = (uintptr_t)format_price;
    memcpy(at + 2, &target, sizeof(target));
    __builtin___clear_cache((char *)at, (char *)(at + 4));
    mprotect((void *)begin, span, PROT_READ | PROT_EXEC);
    installed = 1;
    __android_log_print(ANDROID_LOG_INFO, "Bunker", "Offline regional prices enabled (EUR 0.0057; USD 0.0064)");
    return JNI_TRUE;
}
