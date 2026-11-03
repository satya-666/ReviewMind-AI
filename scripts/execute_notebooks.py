"""Execute all four research notebooks in fresh kernels using this Python environment."""
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

def execute():
    paths=sorted((ROOT/'notebooks').glob('0[1-4]_*.ipynb'))
    if len(paths)!=4:
        raise ValueError('Expected all four Phase 2 research notebooks')
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
            nbformat.write(notebook,path)
            results.append({'notebook':path.name,'code_cells_executed':sum(c.cell_type=='code' for c in notebook.cells),'status':'passed'})
            print('Executed',path.name,flush=True)
    (ROOT/'reports/phase2_notebook_execution.json').write_text(json.dumps({'fresh_kernel_per_notebook':True,
        'interpreter':'active validated Python environment','results':results},indent=2)+'\n')

if __name__=='__main__':
    execute()
