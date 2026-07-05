from pathlib import Path

from ansibleRunner import main
from ansibleRunner.defaults import RuntimeDefaults


def test_main_accepts_project_root_and_argv(tmp_path, capsys):
    result = main(tmp_path, ["--list-defaults"])

    assert result == 0
    output = capsys.readouterr().out
    assert f"project_root={tmp_path.resolve()}" in output
    assert f"log_dir={tmp_path.resolve() / '.ansibleRunner' / 'logs'}" in output


def test_runtime_defaults_are_project_local(tmp_path):
    defaults = RuntimeDefaults.for_project(Path(tmp_path))

    assert defaults.project_root == tmp_path.resolve()
    assert defaults.log_dir == tmp_path.resolve() / ".ansibleRunner" / "logs"
    assert defaults.state_dir == tmp_path.resolve() / ".ansibleRunner" / "state"

