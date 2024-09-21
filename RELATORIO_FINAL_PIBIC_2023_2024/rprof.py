import psutil
import time
import logging
import multiprocessing as mp
from pathlib import Path
from datetime import datetime
import argparse
import sys

process_option_function = {
    'disk': 'io_counters()',
    'memory': 'memory_full_info()',
    'cpu': 'cpu_times()'
}

host_option_function = {
    'disk': 'disk_io_counters()',
    'memory': 'virtual_memory()',
    'cpu': 'cpu_times()'
}

def config():
    """
    The desired options  
    -d for collect disk
    -m             memory
    -c             cpu
    -i for defining the monitoring interval  
    """
    parser = argparse.ArgumentParser(prog='rprof', description='resource usage profiler')

    parser.add_argument('-d', '--disk', action='store_true', help='Collect disk metrics')
    parser.add_argument('-m', '--memory', action='store_true', help='Collect memory metrics')
    parser.add_argument('-c', '--cpu', action='store_true', help='Collect cpu metrics')
    parser.add_argument('-g', '--get-children', action='store_true', help='Include the resource usage from child processes')
    parser.add_argument('-o', '--output_dir', default='.', help='The output dir for the metrics file')
    parser.add_argument('-i', '--interval', type=float, default=1.5, help='Interval in seconds between each metric collection')
    parser.add_argument('-t', '--task_start', help='Date and hour the task started. Used to naming resource graphs.')
    parser.add_argument('command', help='Execution command for the process to be monitored. Must be inside ""')


    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser.parse_args()

def write_data(value_list: list, filename: str, mode: str):

    line = ''
    for value in value_list:
        line += f'{value};'
    
    line = line.strip(';')
    line += '\n'

    with open(filename, mode) as file:
        file.write(line) 

def get_children_data(function, process):

    children = process.children(recursive=True)

    sum = eval(f'process.{function}._asdict()')

    for child in children:
        
        child_data = eval(f'child.{function}._asdict()')
        
        for key, value in sum.items():
            sum[key] = value + child_data[key]
    
    return sum

def collect_data(task_start: str, memory: bool, cpu: bool, disk: bool, get_children: bool, work_dir: Path, process: psutil.Process | psutil.Popen | None, create: bool = False):

    timestamp = datetime.now()

    if not task_start:
        task_start = ""
    else: 
        task_start = f'_{task_start}'
    

    for option in host_option_function.keys():
        if eval(f'{option}'):
            
            if process != None:
                if get_children:
                    data = get_children_data(process_option_function[option], process)
                else:
                    data = eval(f'process.{process_option_function[option]}._asdict()')
            else:
                data = eval(f'psutil.{host_option_function[option]}._asdict()')

            if create:
                write_data(['timestamp'] + list(data.keys()), f'{work_dir}/{option}{task_start}.csv', 'w')
            
            write_data([timestamp] + list(data.values()), f'{work_dir}/{option}{task_start}.csv', 'a')

def run(task_start: str = "", collect_cpu: bool = True, collect_memory: bool = True, collect_disk: bool = True, interval: float = 1.5, process_id: int = -1, collect_child_process_data: bool = False, work_dir: Path = Path('.')):
    
    process = None

    if process_id != -1:
        if psutil.pid_exists(process_id):
            process = psutil.Process(pid=process_id)
        else:
            logging.exception(f'Profiler: Cannot collect data from process {process_id}. Process does not exist')
            return

    collect_data(task_start, collect_memory, collect_cpu, collect_disk, collect_child_process_data, work_dir, process, create=True)

    while True:

        collect_data(task_start, collect_memory, collect_cpu, collect_disk, collect_child_process_data, work_dir, process)
        time.sleep(interval)

if __name__ == '__main__':

    args = config()

    command = args.command.split(' ')

    process = psutil.Popen(command)

    ctx = mp.get_context('spawn')

    data_collection_process = ctx.Process(target=run, args=(args.task_start, args.cpu, args.memory, args.disk, args.interval, process.pid, args.get_children, Path(args.output_dir)))

    data_collection_process.start()

    while process.poll() is None:

        time.sleep(2)
    
    data_collection_process.terminate()