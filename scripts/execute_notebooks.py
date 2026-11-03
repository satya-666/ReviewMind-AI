"""Execute Phase 2 or Phase 3 research notebooks in fresh project Python kernels."""
import json
import os
from pathlib import Path
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('IPYTHONDIR',str(ROOT/'.cache/ipython'))
os.environ.setdefault('JUPYTER_RUNTIME_DIR',str(ROOT/'.cache/jupyter/runtime'))
os.environ.setdefault('JUPYTER_CONFIG_DIR',str(ROOT/'.cache/jupyter/config'))
os.environ.setdefault('JUPYTER_DATA_DIR',str(ROOT/'.cache/jupyter/data'))
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

def execute(phase=2):
    paths=sorted((ROOT/'notebooks').glob('0[1-4]_*.ipynb' if phase==2 else '0[5-7]_*.ipynb'))
    if len(paths)!=(4 if phase==2 else 3):
        raise ValueError(f'Expected all research notebooks for Phase {phase}')
    results=[]
    with tempfile.TemporaryDirectory(prefix='reviewmind-kernel-') as temporary:
        kernel=Path(temporary)/'reviewmind'; kernel.mkdir()
        (kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
            'display_name':'ReviewMind project Python','language':'python'}))
        manager=KernelSpecManager(kernel_dirs=[temporary])
        for path in paths:
            notebook=nbformat.read(path,as_version=4)
            for cell in notebook.cells:
                if cell.cell_type=='code':
                    cell.outputs=[]; cell.execution_count=None
            km=KernelManager(kernel_name='reviewmind',kernel_spec_manager=manager)
            client=NotebookClient(notebook,km=km,timeout=180,resources={'metadata':{'path':str(ROOT)}})
            try:
                client.execute()
            finally:
                if km.has_kernel:
                    km.shutdown_kernel(now=True)
            # Persist executed aggregate outputs; strip machine-specific kernel metadata.
            notebook.metadata['kernelspec']={'name':'python3','display_name':'Python 3','language':'python'}
            for cell in notebook.cells:
                for output in cell.get('outputs',[]):
                    if isinstance(output.get('text'),str):
                        output['text']=output['text'].replace(str(ROOT),'[project]')
                    for mime,value in output.get('data',{}).items():
                        if mime.startswith('text/') and isinstance(value,str):
                            output['data'][mime]=value.replace(str(ROOT),'[project]')
            nbformat.write(notebook,path)
            results.append({'notebook':path.name,'code_cells_executed':sum(c.cell_type=='code' for c in notebook.cells),'status':'passed'})
            print('Executed',path.name,flush=True)
    (ROOT/f'reports/phase{phase}_notebook_execution.json').write_text(json.dumps({'fresh_kernel_per_notebook':True,
        'interpreter':'active validated Python environment','results':results},indent=2)+'\n')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',type=int,choices=[2,3],default=2)
    execute(parser.parse_args().phase)
