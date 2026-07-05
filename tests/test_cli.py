from ansibleRunner import cli


def test_cli_uses_current_directory_by_default(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    result = cli.main(["--list-defaults"])

    assert result == 0
    assert f"project_root={tmp_path.resolve()}" in capsys.readouterr().out

