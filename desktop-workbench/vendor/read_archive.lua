local fs=require 'bee.filesystem'
local mpq=require 'ffi.stormlib'
local archive=assert(mpq.open(fs.path(arg[1]),true),'map archive unreadable')
for _,name in ipairs{'war3map.j','war3map.wtg','war3map.wct','war3map.w3i','(listfile)'} do
    local data=archive:load_file(name)
    if data then
        local out=name=='(listfile)' and 'listfile.txt' or name
        local f=assert(io.open(arg[2]..'/'..out,'wb'));f:write(data);f:close()
    end
end
archive:close()
