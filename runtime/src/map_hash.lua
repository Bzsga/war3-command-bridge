-- LAN protocol hashes, computed with the exact KKWE Lua ABI.
package.cpath=host_module_cpath..package.cpath
require 'filesystem'
local values={require('maphash')(fs.path(arg[2]),fs.path(arg[3]))}
assert(#values==8,'maphash must return eight words')
for i,v in ipairs(values) do values[i]=tostring(v) end
print('['..table.concat(values,',')..']')
