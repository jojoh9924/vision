"""Train on complete sessions; evaluate once on explicitly held-out sessions."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from .cursor_features import CursorFeatures, FEATURE_NAMES, LABELS, WINDOW_SECONDS
from .collect_cursor_data import DATA_DIR
from .cursor_state import DEFAULT_MODEL


def load_sessions(paths):
    features, labels, groups = [], [], []
    for path in paths:
        extractor = CursorFeatures()
        previous = None
        with Path(path).open(newline='') as stream:
            for row in csv.DictReader(stream):
                segment = (row['session'], row['label'], row['mode'])
                if segment != previous:
                    extractor.reset()
                previous = segment
                if row['label'] not in LABELS or row['mode'] not in ('POINT', 'DRAG'):
                    extractor.reset()
                    continue
                values = extractor.update(float(row['timestamp']), float(row['x']), float(row['y']))
                if values is not None:
                    features.append(values)
                    labels.append(row['label'])
                    groups.append(row['session'])
    return np.asarray(features), np.asarray(labels), np.asarray(groups)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=DATA_DIR)
    parser.add_argument('--test-session', action='append', required=True, help='CSV filename reserved for final evaluation; repeat as needed')
    parser.add_argument('--output', type=Path, default=DEFAULT_MODEL)
    parser.add_argument('--exclude-session', action='append', default=[])
    parser.add_argument('--max-depth', type=int, default=10, help='0 means unlimited')
    parser.add_argument('--min-samples-leaf', type=int, default=5)
    parser.add_argument('--trees', type=int, default=100)
    args = parser.parse_args()
    if args.max_depth < 0 or args.min_samples_leaf < 1 or args.trees < 1:
        parser.error('Invalid forest parameters')
    import joblib
    import sklearn
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.metrics import classification_report, confusion_matrix
    files = sorted(args.data_dir.glob('*.csv'))
    excluded = set(args.exclude_session)
    if not excluded.issubset({p.name for p in files}):
        parser.error('Excluded sessions must exist in --data-dir')
    if excluded & set(args.test_session):
        parser.error('Cannot exclude a test session')
    files = [p for p in files if p.name not in excluded]
    test_names = set(args.test_session)
    if not test_names.issubset({p.name for p in files}):
        parser.error('Every --test-session must name a CSV in --data-dir')
    train_files = [p for p in files if p.name not in test_names]
    test_files = [p for p in files if p.name in test_names]
    x, y, groups = load_sessions(train_files)
    xt, yt, test_groups = load_sessions(test_files)
    if len(set(groups)) < 3:
        parser.error('Record at least three training sessions plus a separate test session')
    if set(groups) & set(test_groups):
        parser.error('Session IDs overlap between training and test data')
    for name, labels in [('training', y), ('test', yt)]:
        if set(labels) != set(LABELS):
            parser.error(f'{name} data needs usable windows from all three states')
    model = RandomForestClassifier(n_estimators=args.trees, max_depth=args.max_depth or None,
                                   min_samples_leaf=args.min_samples_leaf, class_weight='balanced',
                                   random_state=42, n_jobs=1)
    cv = GroupKFold(n_splits=min(5, len(set(groups))))
    # Focused sessions may contain two states, but every fitted fold needs all three.
    for train_indices, _ in cv.split(x, y, groups):
        if set(y[train_indices]) != set(LABELS):
            parser.error('Each training fold needs all three states; include more full sessions')
    predictions = cross_val_predict(model, x, y, groups=groups, cv=cv)
    model.fit(x, y)
    test_predictions = model.predict(xt)
    report = classification_report(yt, test_predictions, labels=list(LABELS), output_dict=True, zero_division=0)
    # A deliberately simple speed baseline, with thresholds estimated only from training data.
    centers = np.array([np.median(x[y == label, 1]) for label in LABELS])
    baseline = np.asarray(LABELS)[np.abs(xt[:, 1, None] - centers).argmin(axis=1)]
    metrics = {
        'training_sessions': sorted(set(groups)), 'test_sessions': sorted(set(test_groups)),
        'cross_validation': classification_report(y, predictions, labels=list(LABELS), output_dict=True, zero_division=0),
        'held_out': report,
        'forest_parameters': model.get_params(),
        'excluded_sessions': sorted(excluded),
        'confusion_matrix_labels': LABELS,
        'confusion_matrix': confusion_matrix(yt, test_predictions, labels=list(LABELS)).tolist(),
        'speed_baseline': classification_report(yt, baseline, labels=list(LABELS), output_dict=True, zero_division=0),
        'offline_target_met': all(report[label]['precision'] >= 0.9 and report[label]['recall'] >= 0.9 for label in LABELS),
        'live_validation_complete': False,
        'adaptive_smoothing_enabled': False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({'schema_version': 1, 'features': FEATURE_NAMES,
                 'window_seconds': WINDOW_SECONDS, 'model': model,
                 'sklearn_version': sklearn.__version__, 'metrics': metrics}, args.output)
    args.output.with_suffix('.metrics.json').write_text(json.dumps(metrics, indent=2))
    print(classification_report(yt, test_predictions, labels=list(LABELS), zero_division=0))
    print(f'Saved observation-only model: {args.output}')
    print('Live validation is still required. Cursor smoothing remains unchanged.')


if __name__ == '__main__':
    main()
