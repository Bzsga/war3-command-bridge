-- Independent demo builder: preserves all named payloads, checks index semantics.
-- Caller has already copied the template to a new output; never compact archives.
local ffi=require 'ffi'
local fs=require 'bee.filesystem'
local mpq=require 'ffi.stormlib'
local native=ffi.load('stormlib')
local source=assert(mpq.open(fs.path(arg[1]),true))
local output=assert(mpq.open(fs.path(arg[2]),false))
local f=assert(io.open(arg[3],'rb'));local replacement=f:read('*a');f:close()
local count=source:number_of_files()
assert(output:number_of_files()==count,'copy file count mismatch')
assert(output:save_file('war3map.j',replacement),'script replacement failed')
local module_source=nil
if arg[5] then
    local module=assert(io.open(arg[5],'rb'));module_source=module:read('*a');module:close()
    assert(output:save_file('War3TestBridge.lua',module_source),'bridge module import failed')
end
assert(native.SFileCloseArchive(output.handle));output.handle=0
output=assert(mpq.open(fs.path(arg[2]),true))
local added=module_source and 1 or 0
assert(output:number_of_files()==count+added,'unexpected file count change')
assert(output:load_file('war3map.j')==replacement,'script readback mismatch')
if module_source then assert(output:load_file('War3TestBridge.lua')==module_source,'bridge module readback mismatch') end
local before=assert(source:load_file('(listfile)'))
local after=assert(output:load_file('(listfile)'))
local names={}
local function entries(s)
    local set={}
    for n in s:gmatch('[^\r\n]+') do
        local key=n:gsub('/','\\'):lower()
        set[key]=true;names[key]=n
    end
    return set
end
local a,b=entries(before),entries(after)
for n in pairs(a) do assert(b[n],'index lost name: '..n) end
for n in pairs(b) do assert(a[n] or n=='war3testbridge.lua' or n=='(listfile)' or n=='(attributes)','index added unexpected name: '..n) end
for _,n in ipairs{'war3map.w3i','war3map.w3e','war3map.doo','war3mapUnits.doo','war3map.wpm','war3map.shd','war3map.mmp','war3map.w3a','war3map.w3b','war3map.w3d','war3map.w3h','war3map.w3q','war3map.w3t','war3map.w3u','war3map.wtg','war3map.wct','war3map.wts','war3map.imp','war3mapMisc.txt'} do names[n:lower()]=n end
local verified=0
for key,n in pairs(names) do
    if key~='war3map.j' and key~='war3testbridge.lua' and key~='(listfile)' and key~='(attributes)' then
        assert(source:load_file(n)==output:load_file(n),'payload changed: '..n)
        if source:load_file(n) then verified=verified+1 end
    end
end
local function dump(name,s) local f=assert(io.open(arg[4]..'/'..name,'wb'));f:write(s);f:close() end
dump('listfile-before.txt',before);dump('listfile-after.txt',after)
assert(native.SFileCloseArchive(source.handle));source.handle=0
assert(native.SFileCloseArchive(output.handle));output.handle=0
print(string.format('{"ok":true,"source_files":%d,"files":%d,"named_payloads_unchanged":%d,"script_readback":true,"index_names_preserved":true,"listfile_reserialized":%s}',count,count+added,verified,tostring(before~=after)))
