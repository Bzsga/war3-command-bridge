#include "win32_bootstrap.h"

static HMODULE retained;
DWORD _tls_index;
static wchar_t game[8192],exe[8192],command[32768],path[8192],bundle[8192],temporary[8192];
static BYTE buffer[65536];
static void Mark(const char *text);
static void Number(wchar_t *out,DWORD n);
// KKWE also loads Miles providers. Never hook or launch inside the editor.
static BOOL GameProcess(void) {
    DWORD length=GetModuleFileNameW(NULL,game,8192),start,i;
    static const char *names[]={"war3.exe","warcraft iii.exe"};
    int candidate;
    if(!length||length>=8000)return FALSE;
    start=length;while(start&&game[start-1]!=L'\\'&&game[start-1]!=L'/')start--;
    for(candidate=0;candidate<2;candidate++){
        const char *name=names[candidate];
        for(i=0;name[i]&&game[start+i];i++){
            int c=game[start+i];if(c>='A'&&c<='Z')c+=32;
            if(c!=name[i])break;
        }
        if(!name[i]&&!game[start+i])return TRUE;
    }
    return FALSE;
}
typedef struct {BYTE magic[8];QWORD exeOffset,exeLength,indexOffset,indexLength;BYTE id[16];} FOOTER;
static BOOL ExtractPlayer(void) {
    HANDLE input,output;QWORD size,left;DWORD got,written;FOOTER f;int i;wchar_t id[33];
    static const char magic[]="WVMIX001";static const wchar_t hex[]=L"0123456789abcdef";
    if(!GetModuleFileNameW(retained,bundle,8192))return FALSE;
    input=CreateFileW(bundle,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(input==INVALID_HANDLE_VALUE)return FALSE;
    if(!GetFileSizeEx(input,&size)||size<sizeof(f)||!SetFilePointerEx(input,size-sizeof(f),NULL,0)||!ReadFile(input,&f,sizeof(f),&got,NULL)||got!=sizeof(f)) {CloseHandle(input);return FALSE;}
    for(i=0;i<8;i++)if(f.magic[i]!=(BYTE)magic[i]){CloseHandle(input);return FALSE;}
    if(f.exeOffset<1024||f.exeLength==0||f.exeLength>67108864||f.exeOffset>size||f.exeLength>size-f.exeOffset||f.exeOffset+f.exeLength>f.indexOffset||f.indexOffset>size-sizeof(f)||f.indexLength>1048576||f.indexLength!=size-sizeof(f)-f.indexOffset){CloseHandle(input);return FALSE;}
    for(i=0;i<16;i++){id[2*i]=hex[f.id[i]>>4];id[2*i+1]=hex[f.id[i]&15];}id[32]=0;
    lstrcpyW(exe,game);lstrcatW(exe,L"\\War3Video");CreateDirectoryW(exe,NULL);
    lstrcatW(exe,L"\\cache");CreateDirectoryW(exe,NULL);lstrcatW(exe,L"\\");lstrcatW(exe,id);CreateDirectoryW(exe,NULL);
    lstrcatW(exe,L"\\War3Video.exe");
    output=CreateFileW(exe,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(output!=INVALID_HANDLE_VALUE){QWORD cached=0;GetFileSizeEx(output,&cached);CloseHandle(output);if(cached==f.exeLength){CloseHandle(input);return TRUE;}}
    lstrcpyW(temporary,exe);lstrcatW(temporary,L".partial-");{wchar_t processId[12];Number(processId,GetCurrentProcessId());lstrcatW(temporary,processId);}
    output=CreateFileW(temporary,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(output==INVALID_HANDLE_VALUE){CloseHandle(input);return FALSE;}
    if(!SetFilePointerEx(input,f.exeOffset,NULL,0)){CloseHandle(output);CloseHandle(input);DeleteFileW(temporary);return FALSE;}
    left=f.exeLength;
    while(left){DWORD chunk=left>sizeof(buffer)?sizeof(buffer):(DWORD)left;
        if(!ReadFile(input,buffer,chunk,&got,NULL)||got==0||!WriteFile(output,buffer,got,&written,NULL)||written!=got)break;
        left-=got;
    }
    CloseHandle(output);CloseHandle(input);
    if(left){DeleteFileW(temporary);return FALSE;}
    if(!MoveFileExW(temporary,exe,1)){
        QWORD cached=0;output=CreateFileW(exe,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
        if(output!=INVALID_HANDLE_VALUE){GetFileSizeEx(output,&cached);CloseHandle(output);}DeleteFileW(temporary);
        return cached==f.exeLength;
    }
    Mark("AUTOLOAD embedded player extracted\r\n");return TRUE;
}
static void Number(wchar_t *out,DWORD n) {
    wchar_t tmp[12];int i=0,j=0;
    do {tmp[i++]=(wchar_t)(L'0'+n%10);n/=10;} while(n);
    while(i)out[j++]=tmp[--i];out[j]=0;
}
#include "RequestRouting.c"
static void Mark(const char *text) {
    HANDLE file;DWORD written;
    lstrcpyW(path,game);lstrcatW(path,L"\\War3Video");CreateDirectoryW(path,NULL);
    lstrcatW(path,L"\\bootstrap.log");
    file=CreateFileW(path,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file!=INVALID_HANDLE_VALUE){DWORD size=0;while(text[size])size++;WriteFile(file,text,size,&written,NULL);CloseHandle(file);}
}
static DWORD WINAPI Start(LPVOID unused) {
    STARTUPINFOW startup;PROCESS_INFORMATION process;wchar_t pid[12];DWORD length;
    (void)unused;
    length=GetModuleFileNameW(NULL,game,8192);
    if(length==0||length>=8000)FreeLibraryAndExitThread(retained,0);
    while(length && game[length-1]!=L'\\' && game[length-1]!=L'/')length--;
    if(!length)FreeLibraryAndExitThread(retained,0);game[length-1]=0;
    Mark("AUTOLOAD DLL loaded\r\n");
    InstallRequestRouting();
    // Provision the writable command file before any map initialization runs.
    Number(pid,GetCurrentProcessId());
    lstrcpyW(path,game);lstrcatW(path,L"\\War3Video\\request-");lstrcatW(path,pid);lstrcatW(path,L".pld");
    {HANDLE request=CreateFileW(path,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
     if(request!=INVALID_HANDLE_VALUE)CloseHandle(request);else Mark("ERROR request file initialization failed\r\n");}
    Sleep(1500); // Never initialize WPF or start decoding under the loader lock.
    InstallRequestRouting();
    if(!ExtractPlayer()){Mark("ERROR invalid package or player extraction failed\r\n");FreeLibraryAndExitThread(retained,0);}
    Number(pid,GetCurrentProcessId());
    lstrcpyW(command,L"\"");lstrcatW(command,exe);lstrcatW(command,L"\" --game-root \"");
    lstrcatW(command,game);lstrcatW(command,L"\" --owner-pid ");lstrcatW(command,pid);
    lstrcatW(command,L" --client-pid ");lstrcatW(command,pid);
    lstrcatW(command,L" --bundle \"");lstrcatW(command,bundle);lstrcatW(command,L"\"");
    {volatile unsigned char *p=(volatile unsigned char*)&startup;unsigned i;for(i=0;i<sizeof(startup);i++)p[i]=0;}
    {volatile unsigned char *p=(volatile unsigned char*)&process;unsigned i;for(i=0;i<sizeof(process);i++)p[i]=0;}
    startup.cb=sizeof(startup);startup.dwFlags=STARTF_USESHOWWINDOW;startup.wShowWindow=SW_HIDE;
    if(CreateProcessW(exe,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,game,&startup,&process)) {
        Mark("AUTOLOAD companion started\r\n");CloseHandle(process.hThread);CloseHandle(process.hProcess);
    } else Mark("ERROR companion launch failed\r\n");
    FreeLibraryAndExitThread(retained,0);return 0;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved) {
    (void)reserved;
    if(reason==DLL_PROCESS_ATTACH) {
        HANDLE thread;
        if(!GameProcess())return TRUE;
        DisableThreadLibraryCalls(module);
        if(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,(LPCWSTR)&DllMain,&retained)) {
            thread=CreateThread(NULL,0,Start,NULL,0,NULL);
            if(thread)CloseHandle(thread);else FreeLibrary(retained);
        }
    }
    return TRUE;
}
