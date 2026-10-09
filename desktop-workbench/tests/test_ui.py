import json
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from workbench.ui import Window,STYLE,configure_fonts
from workbench.storage import save,read

def test_project_navigation_params_states_case_save(tmp_path):
    app=QApplication.instance() or QApplication([]);configure_fonts(app);app.setStyleSheet(STYLE)
    p={'schema':1,'id':'uitest','name':'自定义地图','directory':str(tmp_path/'project'),'input_type':'source','map':'author.w3x','source_dir':'','build_argv':[],
       'environment':{},'provider':{'credential':'uitest','base_url':'https://api.deepseek.com','model':''},
       'catalog':{'commands':[{'id':'signal','label':'自定义信号','function':'Signal','params':[{'name':'amount','type':'integer','default':1}]}],
                  'fields':[{'id':'count','label':'次数','type':'integer','source':'global','name':'Count'}]},
       'cases':[{'id':'check_signal','name':'自定义判据','tags':[],'steps':[{'type':'command','op':'snapshot'},{'type':'assert','path':'last.count','operator':'ge','value':0}]}]}
    file=tmp_path/'project/project.json';save(file,p)
    w=Window(tmp_path/'profile');w.timer.stop();w.open_project(file);w.show();app.processEvents()
    w.write_permission.setChecked(True);w.launch_permission.setChecked(True);w.open_project(file)
    assert not w.write_permission.isChecked() and not w.launch_permission.isChecked()
    for i in range(5):w.nav.setCurrentRow(i);app.processEvents();assert w.stack.currentIndex()==i
    w.commands.setCurrentRow(0);w.param_widgets['amount'].setValue(7);assert w.param_widgets['amount'].value()==7
    w.show_state({'count':1});w.show_state({'count':4});assert w.states.item(0,1).text()=='4' and w.states.item(0,2).text()=='1'
    w.case_list.setCurrentRow(0);case=json.loads(w.case_editor.toPlainText());case['name']='修改后的判据';w.case_editor.setPlainText(json.dumps(case));w.save_case();assert read(file)['cases'][0]['name']=='修改后的判据'
    w.logs.appendPlainText('长日志\n'*4000);assert w.logs.document().blockCount()<=3000
    w.resize(980,660);w.side.hide();app.processEvents();assert w.stack.width()>700
    w.close();app.processEvents()
