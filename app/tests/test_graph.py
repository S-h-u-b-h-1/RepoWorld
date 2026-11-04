import pytest

from app.demo import build_demo
from app.graph import MAX_NODES, build_graph, classify, clean_path, group_for_file, parse_imports


def test_demo_has_valid_nodes_and_edges():
    demo = build_demo()
    ids = {node['id'] for node in demo['nodes']}
    assert demo['source'] == 'demo'
    assert len(ids) == len(demo['nodes']) == demo['stats']['modules']
    assert all(e['source'] in ids and e['target'] in ids for e in demo['edges'])
    assert demo['warnings'] and 'Fictional' in demo['warnings'][0]


@pytest.mark.parametrize('path,expected', [
    ('src/components/Button.tsx', 'src/components'),
    ('app/dashboard/page.tsx', 'app/dashboard'),
    ('services/auth/src/login.ts', 'services/auth'),
    ('apps/web/components/Header.tsx', 'apps/web/components'),
    ('docs/architecture/design.md', 'docs/architecture'),
    ('README.md', 'root'),
    ('lib/parser.py', 'lib'),
])
def test_module_grouping(path, expected):
    assert group_for_file(path) == expected


@pytest.mark.parametrize('path', [
    '.env', 'src/.env.production', 'node_modules/a/b.ts',
    'dist/app.js', 'src/../../secret', 'src//file.py',
    'src\\bad.py', 'src/./test.py',
])
def test_skips_unsuitable_paths(path):
    assert clean_path(path) is None


def test_js_import_scanning_and_aliases():
    source = '''
        import { Button } from '../components/Button';
        export { x } from '@/lib/core';
        const api = require('./utils/client');
        import 'core-js';
        import('../../lib/deferred');
    '''
    got = parse_imports(source, 'src/views/page.tsx')
    assert 'src/components/Button' in got
    assert 'src/lib/core' in got
    assert 'src/views/utils/client' in got
    assert 'lib/deferred' in got
    assert 'core-js' not in got


def test_python_imports():
    got = parse_imports('from app.services.auth import Session\nimport app.models.user\n', 'app/views.py')
    assert 'app/services/auth' in got
    assert 'app/models/user' in got


def test_blocks_import_traversal():
    got = parse_imports('import x from "../../../../../../passwd"', 'src/app.ts')
    assert not got


def test_build_graph_shows_bounded_sampled_deps():
    files = [
        {'path': 'src/app.ts', 'type': 'blob'},
        {'path': 'src/components/Button.tsx', 'type': 'blob'},
        {'path': 'src/lib/core.ts', 'type': 'blob'},
        {'path': 'README.md', 'type': 'blob'},
    ]
    graph = build_graph(files, {
        'src/app.ts': "import { Button } from './components/Button'; import { foo } from '@/lib/core'",
    }, name='small')
    ids = {n['id'] for n in graph['nodes']}
    assert ids == {'src', 'src/components', 'src/lib', 'root'}
    assert len(graph['edges']) == 2
    assert {e['target'] for e in graph['edges']} == {'src/components', 'src/lib'}
    assert graph['stats']['inspectedSources'] == 1
    assert any('sampled' in w.lower() for w in graph['warnings'])


def test_build_graph_enforces_node_limit_and_partial_status():
    files = [{'path': f'src/p{i}/app.ts', 'type': 'blob'} for i in range(MAX_NODES + 9)]
    graph = build_graph(files)
    assert len(graph['nodes']) == MAX_NODES
    assert graph['stats']['partial']
    assert graph['stats']['dependencies'] == 0
