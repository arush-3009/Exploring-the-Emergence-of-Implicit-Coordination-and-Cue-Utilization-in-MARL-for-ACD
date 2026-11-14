#jobs that depend on output of other jobs.

import multiprocessing
import traceback
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import redirect_stderr, redirect_stdout

import torch


def _logged(label, work, log) -> None:
    
    log.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting {label}", flush=True)
    
    with log.open("w", buffering=1) as stream, redirect_stdout(stream), redirect_stderr(stream):
        try:
            work()
        except Exception:
            traceback.print_exc(file=stream)
            raise
        
    print(f"Finished {label}", flush=True)



def _one_torch_thread() -> None:
    torch.set_num_threads(1)




def _ready(works: dict, needs: dict, started: set, done: set) -> list:

    ready = []
    for label in works:
        
        if label in started:
            continue
        
        waiting = False
        
        for need in needs[label]:
            if need not in done:
                waiting = True
                
        if not waiting:
            ready.append(label)

    return ready



def run_jobs(works: dict, needs: dict, logs: dict, workers: int) -> None:

    if workers == 1:
        _run_serially(works, needs, logs)
    else:
        _run_in_parallel(works, needs, logs, workers)



def _run_serially(works: dict, needs: dict, logs: dict) -> None:

    previous_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    done = set()

    try:
        while len(done) < len(works):
            
            ready = _ready(works, needs, done, done)
            if not ready:
                raise RuntimeError("the remaining jobs wait for each other")
            
            label = ready[0]
            try:
                _logged(label, works[label], logs[label])
            except Exception as error:
                raise RuntimeError(f"{label} failed, see {logs[label]}") from error
            
            done.add(label)
            
    finally:
        torch.set_num_threads(previous_threads)


def _run_in_parallel(works: dict, needs: dict, logs: dict, workers: int) -> None:

    started = set()
    done = set()
    running = {}

    with ProcessPoolExecutor(max_workers=workers,
                             mp_context=multiprocessing.get_context("spawn"),
                             initializer=_one_torch_thread) as pool:
        
        try:
            while len(done) < len(works):
                
                for label in _ready(works, needs, started, done):
                    running[pool.submit(_logged, label, works[label], logs[label])] = label
                    started.add(label)
                    
                if not running:
                    raise RuntimeError("the remaining jobs wait for each other")

                finished, _ = wait(running, return_when=FIRST_COMPLETED)
                
                for future in finished:
                    label = running.pop(future)
                    
                    try:
                        future.result()
                    except Exception as error:
                        raise RuntimeError(f"{label} failed, see {logs[label]}") from error
                    
                    done.add(label)
                    
        finally:
            for future in running:
                future.cancel()


