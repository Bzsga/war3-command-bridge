// Minimal 32-bit Windows ABI declarations; no CRT dependency.
typedef unsigned short wchar_t;
typedef unsigned long DWORD;
typedef unsigned short WORD;
typedef unsigned char BYTE;
typedef unsigned long long QWORD;
typedef int BOOL;
typedef void *HANDLE;
typedef void *HMODULE;
typedef void *HINSTANCE;
typedef void *LPVOID;
typedef const wchar_t *LPCWSTR;
#define WINAPI __attribute__((stdcall))
#define API __declspec(dllimport)
#define TRUE 1
#define FALSE 0
#define NULL ((void*)0)
#define DLL_PROCESS_ATTACH 1
#define GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS 4
#define STARTF_USESHOWWINDOW 1
#define SW_HIDE 0
#define CREATE_NO_WINDOW 0x08000000
#define FILE_APPEND_DATA 4
#define FILE_SHARE_READ 1
#define FILE_SHARE_WRITE 2
#define GENERIC_READ 0x80000000
#define GENERIC_WRITE 0x40000000
#define OPEN_EXISTING 3
#define CREATE_ALWAYS 2
#define OPEN_ALWAYS 4
#define FILE_ATTRIBUTE_NORMAL 128
#define INVALID_FILE_ATTRIBUTES ((DWORD)0xffffffff)
#define INVALID_HANDLE_VALUE ((HANDLE)-1)
typedef struct {
    DWORD cb;wchar_t *lpReserved,*lpDesktop,*lpTitle;
    DWORD dwX,dwY,dwXSize,dwYSize,dwXCountChars,dwYCountChars,dwFillAttribute,dwFlags;
    WORD wShowWindow,cbReserved2;BYTE *lpReserved2;HANDLE hStdInput,hStdOutput,hStdError;
} STARTUPINFOW;
typedef struct {HANDLE hProcess,hThread;DWORD dwProcessId,dwThreadId;} PROCESS_INFORMATION;
typedef DWORD (WINAPI *THREADPROC)(LPVOID);
API DWORD WINAPI GetModuleFileNameW(HMODULE,wchar_t*,DWORD);
API __declspec(noreturn) void WINAPI FreeLibraryAndExitThread(HMODULE,DWORD);
API BOOL WINAPI GetModuleHandleExW(DWORD,LPCWSTR,HMODULE*);
API BOOL WINAPI DisableThreadLibraryCalls(HMODULE);
API HANDLE WINAPI CreateThread(LPVOID,DWORD,THREADPROC,LPVOID,DWORD,DWORD*);
API BOOL WINAPI CloseHandle(HANDLE);
API void WINAPI Sleep(DWORD);
API wchar_t *WINAPI lstrcpyW(wchar_t*,LPCWSTR);
API wchar_t *WINAPI lstrcatW(wchar_t*,LPCWSTR);
API BOOL WINAPI CreateDirectoryW(LPCWSTR,LPVOID);
API HANDLE WINAPI CreateFileW(LPCWSTR,DWORD,DWORD,LPVOID,DWORD,DWORD,HANDLE);
API BOOL WINAPI WriteFile(HANDLE,const void*,DWORD,DWORD*,LPVOID);
API DWORD WINAPI GetFileAttributesW(LPCWSTR);
API DWORD WINAPI GetCurrentProcessId(void);
API BOOL WINAPI CreateProcessW(LPCWSTR,wchar_t*,LPVOID,LPVOID,BOOL,DWORD,LPVOID,LPCWSTR,STARTUPINFOW*,PROCESS_INFORMATION*);
API BOOL WINAPI FreeLibrary(HMODULE);
API BOOL WINAPI ReadFile(HANDLE,void*,DWORD,DWORD*,LPVOID);
API BOOL WINAPI GetFileSizeEx(HANDLE,QWORD*);
API BOOL WINAPI SetFilePointerEx(HANDLE,QWORD,QWORD*,DWORD);
API BOOL WINAPI MoveFileExW(LPCWSTR,LPCWSTR,DWORD);
API BOOL WINAPI DeleteFileW(LPCWSTR);
API HMODULE WINAPI GetModuleHandleW(LPCWSTR);
API LPVOID WINAPI GetProcAddress(HMODULE,const char*);
API BOOL WINAPI VirtualProtect(LPVOID,DWORD,DWORD,DWORD*);
API HANDLE WINAPI CreateToolhelp32Snapshot(DWORD,DWORD);
API BOOL WINAPI Module32FirstW(HANDLE,LPVOID);
API BOOL WINAPI Module32NextW(HANDLE,LPVOID);
