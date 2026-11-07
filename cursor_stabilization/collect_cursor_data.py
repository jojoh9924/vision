"""Run with python -m cursor_stabilization.collect_cursor_data."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import uuid
import math

DATA_DIR = Path(__file__).parent / 'data'


class Recorder:
    def __init__(self, directory=DATA_DIR, guided=False, focus=False):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.session = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
        self.path = directory / (self.session + '.csv')
        self.file = self.path.open('x', newline='')
        self.writer = csv.writer(self.file)
        self.writer.writerow(['session', 'timestamp', 'x', 'y', 'mode', 'label'])
        self.guided = guided or focus
        self.sequence = (('STATIONARY', 'PRECISION') * 3 if focus else
                         ('STATIONARY', 'PRECISION', 'MOVING', 'PRECISION', 'STATIONARY', 'MOVING'))
        self.started_at = None
        self.done = False
        self.prompt = ''
        self.label = ''
        self.ready_at = float('inf')
        print(f'Recording to {self.path}')

    def select(self, key, timestamp):
        if self.guided:
            return
        labels = {ord('1'): 'STATIONARY', ord('2'): 'PRECISION', ord('3'): 'MOVING', ord('0'): ''}
        if key in labels:
            self.label = labels[key]
            self.ready_at = timestamp + 0.5

    def write(self, timestamp, x, y, mode):
        if self.guided:
            if self.started_at is None:
                self.started_at = timestamp
            elapsed = timestamp - self.started_at
            # Two rounds in different orders reduce dependence on exercise order.
            sequence = self.sequence
            index = int(elapsed // 35)
            self.done = index >= len(sequence)
            if self.done:
                self.label = ''
                self.prompt = 'DONE - recording saved'
            else:
                phase = elapsed % 35
                target = sequence[index]
                self.label = target if phase >= 5 else ''
                self.ready_at = timestamp if phase >= 5 else float('inf')
                remaining = math.ceil((35 if phase >= 5 else 5) - phase)
                instruction = {'STATIONARY': 'Hold one point; tremor is OK', 'PRECISION': 'Small deliberate moves', 'MOVING': 'Broad sweeps inside box'}[target]
                self.prompt = f'{index+1}/{len(sequence)} {instruction}: {remaining}s' if phase >= 5 else f'Get ready: {instruction} ({remaining}s)'
        label = self.label if timestamp >= self.ready_at and mode in ('POINT', 'DRAG') else ''
        self.writer.writerow([self.session, timestamp, x, y, mode, label])

    def close(self):
        self.file.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Record labeled hand motion; 1=hold, 2=fine adjustment, 3=sweep, 0=pause, q=quit')
    parser.add_argument('--data-dir', type=Path, default=DATA_DIR)
    parser.add_argument('--guided', action='store_true', help='Automatic six-exercise session with countdowns')
    parser.add_argument('--focus', action='store_true', help='Guided stationary/precision collection only (3.5 minutes)')
    args = parser.parse_args()
    from .recording_app import main as run_cursor
    recorder = Recorder(args.data_dir, guided=args.guided, focus=args.focus)
    try:
        run_cursor(recorder=recorder)
    finally:
        recorder.close()


if __name__ == '__main__':
    main()
