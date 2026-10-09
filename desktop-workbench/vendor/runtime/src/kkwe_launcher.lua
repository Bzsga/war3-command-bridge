-- Uses the same KKWE sys.process injection API as share/script/util.lua.
package.cpath=host_module_cpath..package.cpath
require 'sys'
require 'filesystem'
local process=sys.process()
assert(process:inject(fs.path(arg[4]))~=false,'KKWE injection setup failed')
assert(process:create(fs.path(arg[2]..'/war3.exe'),arg[3],fs.path(arg[2])),'KKWE injected launch failed')
host_record_process(process:id())
print('KKWE spawn_inject completed; unique map, no shared test-copy write')
while process:is_running() and not host_should_stop() do host_sleep() end
if process:is_running() then process:kill() end
process:close()
print('Owned KKWE game process stopped')
