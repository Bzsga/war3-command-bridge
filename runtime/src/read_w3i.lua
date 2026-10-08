local fs=require 'bee.filesystem'
local mpq=require 'ffi.stormlib'
local map=assert(mpq.open(fs.path(arg[1]),true))
local data=assert(map:load_file('war3map.w3i'))
map:close()
local f=assert(io.open(arg[2],'wb'));f:write(data);f:close()
