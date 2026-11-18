#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include <ctype.h>

#pragma comment(linker, "/export:D3DAssemble=d3dcompiler_46_orig.D3DAssemble")
#pragma comment(linker, "/export:D3DCompile=d3dcompiler_46_orig.D3DCompile")
#pragma comment(linker, "/export:D3DCompile2=d3dcompiler_46_orig.D3DCompile2")
#pragma comment(linker, "/export:D3DCompileFromFile=d3dcompiler_46_orig.D3DCompileFromFile")
#pragma comment(linker, "/export:D3DCompressShaders=d3dcompiler_46_orig.D3DCompressShaders")
#pragma comment(linker, "/export:D3DCreateBlob=d3dcompiler_46_orig.D3DCreateBlob")
#pragma comment(linker, "/export:D3DDecompressShaders=d3dcompiler_46_orig.D3DDecompressShaders")
#pragma comment(linker, "/export:D3DDisassemble=d3dcompiler_46_orig.D3DDisassemble")
#pragma comment(linker, "/export:D3DDisassemble10Effect=d3dcompiler_46_orig.D3DDisassemble10Effect")
#pragma comment(linker, "/export:D3DDisassemble11Trace=d3dcompiler_46_orig.D3DDisassemble11Trace")
#pragma comment(linker, "/export:D3DDisassembleRegion=d3dcompiler_46_orig.D3DDisassembleRegion")
#pragma comment(linker, "/export:D3DGetBlobPart=d3dcompiler_46_orig.D3DGetBlobPart")
#pragma comment(linker, "/export:D3DGetDebugInfo=d3dcompiler_46_orig.D3DGetDebugInfo")
#pragma comment(linker, "/export:D3DGetInputAndOutputSignatureBlob=d3dcompiler_46_orig.D3DGetInputAndOutputSignatureBlob")
#pragma comment(linker, "/export:D3DGetInputSignatureBlob=d3dcompiler_46_orig.D3DGetInputSignatureBlob")
#pragma comment(linker, "/export:D3DGetOutputSignatureBlob=d3dcompiler_46_orig.D3DGetOutputSignatureBlob")
#pragma comment(linker, "/export:D3DGetTraceInstructionOffsets=d3dcompiler_46_orig.D3DGetTraceInstructionOffsets")
#pragma comment(linker, "/export:D3DPreprocess=d3dcompiler_46_orig.D3DPreprocess")
#pragma comment(linker, "/export:D3DReadFileToBlob=d3dcompiler_46_orig.D3DReadFileToBlob")
#pragma comment(linker, "/export:D3DReflect=d3dcompiler_46_orig.D3DReflect")
#pragma comment(linker, "/export:D3DReturnFailure1=d3dcompiler_46_orig.D3DReturnFailure1")
#pragma comment(linker, "/export:D3DSetBlobPart=d3dcompiler_46_orig.D3DSetBlobPart")
#pragma comment(linker, "/export:D3DStripShader=d3dcompiler_46_orig.D3DStripShader")
#pragma comment(linker, "/export:D3DWriteBlobToFile=d3dcompiler_46_orig.D3DWriteBlobToFile")
#pragma comment(linker, "/export:DebugSetMute=d3dcompiler_46_orig.DebugSetMute")

static uint8_t* g_gfxData = nullptr;
static int64_t g_gfxSize = 0;

struct StreamSlot {
    void* file;
    int64_t pos;
};
static const int MAX_STREAMS = 16;
static StreamSlot g_streams[MAX_STREAMS] = {};
static CRITICAL_SECTION g_cs;

typedef void* (*OpenFileFn)(void* loaderImpl, const char* path, int loadConstants);
static OpenFileFn g_origOpenFile = nullptr;
static void* g_patchedVtable[32] = { nullptr };
static bool g_vtableInit = false;

static int GetSlotLocked(void* self) {
    for (int i = 0; i < MAX_STREAMS; ++i) {
        if (g_streams[i].file == self) return i;
    }
    return -1;
}

static void RegisterStream(void* self) {
    EnterCriticalSection(&g_cs);
    int idx = GetSlotLocked(self);
    if (idx >= 0) {
        g_streams[idx].pos = 0;
    } else {
        for (int i = 0; i < MAX_STREAMS; ++i) {
            if (g_streams[i].file == nullptr) {
                g_streams[i].file = self;
                g_streams[i].pos = 0;
                break;
            }
        }
    }
    LeaveCriticalSection(&g_cs);
}

static int64_t HookLTell(void* self) {
    EnterCriticalSection(&g_cs);
    int idx = GetSlotLocked(self);
    int64_t p = (idx >= 0) ? g_streams[idx].pos : 0;
    LeaveCriticalSection(&g_cs);
    return p;
}

static int HookTell(void* self) { return (int)HookLTell(self); }
static int HookGetLength(void* self) { return (int)g_gfxSize; }
static int64_t HookLGetLength(void* self) { return g_gfxSize; }

static int HookBytesAvailable(void* self) {
    int64_t avail = g_gfxSize - HookLTell(self);
    return avail > 0 ? (int)avail : 0;
}

static int HookRead(void* self, uint8_t* pbuf, int numBytes) {
    if (!g_gfxData || !pbuf || numBytes <= 0) return 0;
    EnterCriticalSection(&g_cs);
    int idx = GetSlotLocked(self);
    int64_t pos = (idx >= 0) ? g_streams[idx].pos : 0;
    int64_t avail = g_gfxSize - pos;
    int toRead = 0;
    if (avail > 0) {
        toRead = (int)(numBytes < avail ? numBytes : avail);
        memcpy(pbuf, g_gfxData + pos, (size_t)toRead);
        if (idx >= 0) g_streams[idx].pos = pos + toRead;
    }
    LeaveCriticalSection(&g_cs);
    return toRead;
}

static int HookSkipBytes(void* self, int numBytes) {
    if (numBytes <= 0) return 0;
    EnterCriticalSection(&g_cs);
    int idx = GetSlotLocked(self);
    int64_t pos = (idx >= 0) ? g_streams[idx].pos : 0;
    int64_t avail = g_gfxSize - pos;
    int skipped = 0;
    if (avail > 0) {
        skipped = (int)(numBytes < avail ? numBytes : avail);
        if (idx >= 0) g_streams[idx].pos = pos + skipped;
    }
    LeaveCriticalSection(&g_cs);
    return skipped;
}

static int64_t HookLSeek(void* self, int64_t offset, int origin) {
    EnterCriticalSection(&g_cs);
    int idx = GetSlotLocked(self);
    int64_t pos = (idx >= 0) ? g_streams[idx].pos : 0;
    int64_t newPos = pos;
    if (origin == 0) newPos = offset;
    else if (origin == 1) newPos = pos + offset;
    else if (origin == 2) newPos = g_gfxSize - offset;
    if (newPos < 0) newPos = 0;
    if (newPos > g_gfxSize) newPos = g_gfxSize;
    if (idx >= 0) g_streams[idx].pos = newPos;
    LeaveCriticalSection(&g_cs);
    return newPos;
}

static int HookSeek(void* self, int offset, int origin) {
    return (int)HookLSeek(self, (int64_t)offset, origin);
}

static bool StrContainsInsensitive(const char* hay, const char* needle) {
    if (!hay || !needle) return false;
    size_t nlen = strlen(needle);
    for (const char* p = hay; *p; ++p) {
        size_t i = 0;
        while (i < nlen && p[i] && tolower((unsigned char)p[i]) == tolower((unsigned char)needle[i])) {
            ++i;
        }
        if (i == nlen) return true;
    }
    return false;
}

static void* HookOpenFile(void* loaderImpl, const char* path, int loadConstants) {
    void* file = g_origOpenFile(loaderImpl, path, loadConstants);
    if (file && g_gfxData && StrContainsInsensitive(path, "coh2ui.gfx")) {
        EnterCriticalSection(&g_cs);
        void** origVtable = *(void***)file;
        if (origVtable && origVtable != g_patchedVtable && !g_vtableInit) {
            for (int i = 0; i < 32; ++i) g_patchedVtable[i] = origVtable[i];
            g_patchedVtable[4]  = (void*)&HookTell;
            g_patchedVtable[5]  = (void*)&HookLTell;
            g_patchedVtable[6]  = (void*)&HookGetLength;
            g_patchedVtable[7]  = (void*)&HookLGetLength;
            g_patchedVtable[10] = (void*)&HookRead;
            g_patchedVtable[11] = (void*)&HookSkipBytes;
            g_patchedVtable[12] = (void*)&HookBytesAvailable;
            g_patchedVtable[14] = (void*)&HookSeek;
            g_patchedVtable[15] = (void*)&HookLSeek;
            g_vtableInit = true;
        }
        LeaveCriticalSection(&g_cs);
        if (g_vtableInit) {
            RegisterStream(file);
            *(void***)file = g_patchedVtable;
        }
    }
    return file;
}

static bool LoadGfxOverride(HMODULE hSelf) {
    wchar_t path[MAX_PATH];
    DWORD len = GetModuleFileNameW(hSelf, path, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) return false;
    wchar_t* slash = wcsrchr(path, L'\\');
    if (!slash) return false;
    wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), L"coh2ui_redir.gfx");

    HANDLE hFile = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (hFile == INVALID_HANDLE_VALUE) return false;

    LARGE_INTEGER sz;
    if (!GetFileSizeEx(hFile, &sz) || sz.QuadPart <= 0 || sz.QuadPart > 300 * 1024 * 1024) {
        CloseHandle(hFile);
        return false;
    }

    g_gfxSize = (int64_t)sz.QuadPart;
    g_gfxData = (uint8_t*)VirtualAlloc(nullptr, (SIZE_T)g_gfxSize, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!g_gfxData) {
        CloseHandle(hFile);
        return false;
    }

    uint8_t* ptr = g_gfxData;
    size_t rem = (size_t)g_gfxSize;
    while (rem > 0) {
        DWORD chunk = rem > 0x40000000 ? 0x40000000 : (DWORD)rem;
        DWORD got = 0;
        if (!ReadFile(hFile, ptr, chunk, &got, nullptr) || got == 0) {
            CloseHandle(hFile);
            VirtualFree(g_gfxData, 0, MEM_RELEASE);
            g_gfxData = nullptr;
            return false;
        }
        ptr += got;
        rem -= got;
    }
    CloseHandle(hFile);
    return true;
}

static void InstallHook() {
    uint8_t* base = (uint8_t*)GetModuleHandleW(nullptr);
    if (!base) return;
    // RelicCoH2.exe (64-bit Steam build, warnings.log: exe 0x00005f10:data 0x0e2b5016)
    uint8_t* target = base + 0x172B7D0;
    const uint8_t expected[16] = {
        0x48, 0x89, 0x5C, 0x24, 0x08,
        0x57,
        0x48, 0x83, 0xEC, 0x30,
        0x48, 0x8B, 0xD9,
        0x48, 0x8B, 0xFA
    };
    if (memcmp(target, expected, sizeof(expected)) != 0) return;

    uint8_t* tramp = (uint8_t*)VirtualAlloc(nullptr, 64, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tramp) return;
    memcpy(tramp, target, 16);
    tramp[16] = 0xFF; tramp[17] = 0x25;
    *(uint32_t*)(tramp + 18) = 0;
    *(uint64_t*)(tramp + 22) = (uint64_t)(target + 16);
    g_origOpenFile = (OpenFileFn)tramp;

    DWORD oldProt = 0;
    if (VirtualProtect(target, 16, PAGE_EXECUTE_READWRITE, &oldProt)) {
        target[0] = 0xFF; target[1] = 0x25;
        *(uint32_t*)(target + 2) = 0;
        *(uint64_t*)(target + 6) = (uint64_t)&HookOpenFile;
        target[14] = 0x90; target[15] = 0x90;
        VirtualProtect(target, 16, oldProt, &oldProt);
        FlushInstructionCache(GetCurrentProcess(), target, 16);
    }
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        InitializeCriticalSection(&g_cs);
        if (LoadGfxOverride(hModule)) InstallHook();
    }
    return TRUE;
}
