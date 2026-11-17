"""Native CTest runner regression independent of MPFR: no zero-test success."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def _build(tmp_path, on):
    src = tmp_path / 'src'; src.mkdir()
    text = ['cmake_minimum_required(VERSION 3.16)',
            'project(ctest_gate LANGUAGES NONE)',
            'option(RAMPD_BUILD_TESTS "test guard" ON)',
            'if(RAMPD_BUILD_TESTS)', ' enable_testing()']
    text.extend(' add_test(NAME %s_cpp COMMAND ${CMAKE_COMMAND} -E true)' % n
                for n in ('interval','picard','abi'))
    text.append('endif()')
    (src/'CMakeLists.txt').write_text('\n'.join(text)+'\n')
    build=tmp_path/'build'
    r=subprocess.run(['cmake','-S',str(src),'-B',str(build),
                      '-DRAMPD_BUILD_TESTS='+('ON' if on else 'OFF')],
                     capture_output=True,text=True)
    assert r.returncode==0, r.stderr
    return build


def _run(build,tmp_path):
    return subprocess.run([sys.executable,str(ROOT/'scripts/check_native_ctest.py'),
                           str(build),'--log',str(tmp_path/'ctest.log')],
                          capture_output=True,text=True)


def test_mandatory_three_tests_are_actually_run(tmp_path):
    b = _build(tmp_path,True)
    r = _run(b,tmp_path)
    assert r.returncode == 0, (r.stdout,r.stderr)
    assert json.loads(r.stdout)['passed'] == 3
    assert '100% tests passed' in (tmp_path/'ctest.log').read_text()


def test_zero_tests_not_a_false_success(tmp_path):
    b = _build(tmp_path,False)
    r = _run(b,tmp_path)
    assert r.returncode == 2
    assert ('native tests NOT run' in (tmp_path/'ctest.log').read_text() or
            'RAMPD_BUILD_TESTS=ON' in (tmp_path/'ctest.log').read_text())
