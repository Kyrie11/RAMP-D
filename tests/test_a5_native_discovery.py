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


def _custom_build(tmp_path, entries, properties=()):
    src = tmp_path / 'src'; src.mkdir()
    config = ['cmake_minimum_required(VERSION 3.16)',
              'project(ctest_gate LANGUAGES NONE)',
              'option(RAMPD_BUILD_TESTS "test guard" ON)', 'enable_testing()']
    config += ['add_test(NAME %s COMMAND ${CMAKE_COMMAND} -E %s)' % (name, cmd)
               for name, cmd in entries]
    config += list(properties)
    (src / 'CMakeLists.txt').write_text('\n'.join(config) + '\n')
    build = tmp_path / 'build'
    subprocess.run(['cmake', '-S', str(src), '-B', str(build),
                    '-DRAMPD_BUILD_TESTS=ON'], check=True, capture_output=True, text=True)
    return build


def test_missing_cache_and_disabled_configuration_rejected(tmp_path):
    build = tmp_path / 'build'; build.mkdir()
    (build / 'CTestTestfile.cmake').write_text('# zero tests\n')
    assert _run(build, tmp_path).returncode == 2
    assert 'no configured RAMPD_BUILD_TESTS=ON' in (tmp_path/'ctest.log').read_text()
    (build/'CMakeCache.txt').write_text('//RAMPD_BUILD_TESTS:BOOL=ON\nRAMPD_BUILD_TESTS:BOOL=OFF\n')
    assert _run(build, tmp_path).returncode == 2
    assert 'no configured RAMPD_BUILD_TESTS=ON' in (tmp_path/'ctest.log').read_text()


def test_zero_tests_with_valid_cache(tmp_path):
    build = _custom_build(tmp_path, [])
    assert _run(build, tmp_path).returncode == 2
    assert 'missing mandatory native tests' in (tmp_path/'ctest.log').read_text()


def test_similar_test_names_do_not_count(tmp_path):
    build = _custom_build(tmp_path, [('not_interval_cpp', 'true'),
                                    ('picard_cpp_extra', 'true'), ('abi_cpp', 'true')])
    assert _run(build, tmp_path).returncode == 2
    assert 'missing mandatory native tests' in (tmp_path/'ctest.log').read_text()


def test_native_failure_not_pass(tmp_path):
    build = _custom_build(tmp_path, [('interval_cpp','false'),
                                    ('picard_cpp','true'), ('abi_cpp','true')])
    assert _run(build, tmp_path).returncode == 2
    assert 'native test execution incomplete or failed' in (tmp_path/'ctest.log').read_text()


def test_native_disabled_not_pass(tmp_path):
    build = _custom_build(tmp_path, [(n, 'true') for n in ('interval_cpp','picard_cpp','abi_cpp')],
                          ['set_tests_properties(interval_cpp PROPERTIES DISABLED TRUE)'])
    assert _run(build, tmp_path).returncode == 2


def test_native_skipped_not_pass(tmp_path):
    build = _custom_build(tmp_path, [(n, 'true') for n in ('interval_cpp','picard_cpp','abi_cpp')],
                          ['set_tests_properties(interval_cpp PROPERTIES SKIP_RETURN_CODE 0)'])
    assert _run(build, tmp_path).returncode == 2
    assert 'native test execution incomplete or failed' in (tmp_path/'ctest.log').read_text()
