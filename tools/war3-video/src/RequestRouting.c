// Route only the presentation request file, in this process's import tables.
// No game offsets, instructions, custom JASS natives or shared game state.
typedef HANDLE (WINAPI *CREATE_A)(const char*,DWORD,DWORD,LPVOID,DWORD,DWORD,HANDLE);
typedef HANDLE (WINAPI *CREATE_W)(LPCWSTR,DWORD,DWORD,LPVOID,DWORD,DWORD,HANDLE);
static CREATE_A originalA;
static CREATE_W originalW;
static wchar_t channel[32];
static int Equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int Fold(int c){if(c=='/')return '\\';if(c>='A'&&c<='Z')return c+32;return c;}
static int MatchA(const char *name,int *length){const char *suffix="war3video\\request.pld";int n=0,i;while(name[n]&&n<1000)n++;*length=n;if(n<21||n>=1000)return 0;for(i=0;i<21;i++)if(Fold((unsigned char)name[n-21+i])!=suffix[i])return 0;return n==21||Fold(name[n-22])=='\\';}
static int MatchW(LPCWSTR name,int *length){const char *suffix="war3video\\request.pld";int n=0,i;while(name[n]&&n<1000)n++;*length=n;if(n<21||n>=1000)return 0;for(i=0;i<21;i++)if(Fold(name[n-21+i])!=suffix[i])return 0;return n==21||Fold(name[n-22])=='\\';}
static HANDLE WINAPI RouteA(const char *name,DWORD access,DWORD share,LPVOID security,DWORD creation,DWORD flags,HANDLE templateFile){int n,i,j;char routed[1050];if(name&&MatchA(name,&n)){for(i=0;i<n-4;i++)routed[i]=name[i];routed[i++]='-';for(j=0;channel[j];j++)routed[i++]=(char)channel[j];routed[i++]='.';routed[i++]='p';routed[i++]='l';routed[i++]='d';routed[i]=0;name=routed;}return originalA(name,access,share,security,creation,flags,templateFile);}
static HANDLE WINAPI RouteW(LPCWSTR name,DWORD access,DWORD share,LPVOID security,DWORD creation,DWORD flags,HANDLE templateFile){int n,i,j;wchar_t routed[1050];if(name&&MatchW(name,&n)){for(i=0;i<n-4;i++)routed[i]=name[i];routed[i++]=L'-';for(j=0;channel[j];j++)routed[i++]=channel[j];routed[i++]=L'.';routed[i++]=L'p';routed[i++]=L'l';routed[i++]=L'd';routed[i]=0;name=routed;}return originalW(name,access,share,security,creation,flags,templateFile);}
typedef struct {DWORD size,moduleId,processId,globalUsage,processUsage;BYTE *base;DWORD baseSize;HMODULE module;wchar_t name[256],path[260];} MODULE_ENTRY;
static void PatchImports(BYTE *base,DWORD size){DWORD pe,rva,bytes,at;if(size<256||*(WORD*)base!=0x5a4d)return;pe=*(DWORD*)(base+60);if(pe>size-136||*(DWORD*)(base+pe)!=0x4550||*(WORD*)(base+pe+24)!=0x10b)return;rva=*(DWORD*)(base+pe+128);bytes=*(DWORD*)(base+pe+132);if(!rva||rva>size||bytes>size-rva)return;
 for(at=rva;at+20<=rva+bytes;at+=20){DWORD names=*(DWORD*)(base+at),slots=*(DWORD*)(base+at+16),i;if(!slots)break;if(!names||names>=size||slots>=size)continue;
  for(i=0;names+i+4<=size&&slots+i+4<=size;i+=4){DWORD name=*(DWORD*)(base+names+i),old;LPVOID hook=NULL;DWORD *slot=(DWORD*)(base+slots+i);if(!name)break;if(name&0x80000000||name>size-32)continue;if(Equal((char*)(base+name+2),"CreateFileA"))hook=(LPVOID)&RouteA;else if(Equal((char*)(base+name+2),"CreateFileW"))hook=(LPVOID)&RouteW;if(hook&&*slot!=(DWORD)hook&&VirtualProtect(slot,4,4,&old)){*slot=(DWORD)hook;VirtualProtect(slot,4,old,&old);}
  }
 }
}
static void InstallRequestRouting(void){HANDLE snapshot;MODULE_ENTRY entry;HMODULE kernel=GetModuleHandleW(L"kernel32.dll"),baseKernel=GetModuleHandleW(L"kernelbase.dll"),nt=GetModuleHandleW(L"ntdll.dll");if(!originalA){originalA=(CREATE_A)GetProcAddress(kernel,"CreateFileA");originalW=(CREATE_W)GetProcAddress(kernel,"CreateFileW");Number(channel,GetCurrentProcessId());}if(!originalA||!originalW)return;snapshot=CreateToolhelp32Snapshot(8|16,GetCurrentProcessId());if(snapshot==INVALID_HANDLE_VALUE)return;entry.size=sizeof(entry);if(Module32FirstW(snapshot,&entry)){do{if(entry.module!=retained&&entry.module!=kernel&&entry.module!=baseKernel&&entry.module!=nt)PatchImports(entry.base,entry.baseSize);}while(Module32NextW(snapshot,&entry));}CloseHandle(snapshot);}
