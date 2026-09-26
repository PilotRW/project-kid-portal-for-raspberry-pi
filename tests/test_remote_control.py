from subprocess import CompletedProcess

from app.services.remote_control import RemoteControlService


def test_pointer_moves_with_fixed_safe_steps(monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("app.services.remote_control.subprocess.run", fake_run)
    service = RemoteControlService(command="xdotool", xauthority="")

    service.control_pointer("left")
    service.control_pointer("down")
    service.control_pointer("click")
    service.control_pointer("scroll_up")
    service.control_pointer("scroll_down")

    assert commands == [
        ["xdotool", "mousemove_relative", "--", "-56", "0"],
        ["xdotool", "mousemove_relative", "--", "0", "56"],
        ["xdotool", "click", "1"],
        ["xdotool", "click", "--repeat", "3", "--delay", "20", "4"],
        ["xdotool", "click", "--repeat", "3", "--delay", "20", "5"],
    ]


def test_pointer_rejects_unknown_actions():
    service = RemoteControlService(command="xdotool", xauthority="")

    try:
        service.control_pointer("drag")
    except ValueError as error:
        assert str(error) == "Unsupported pointer action"
    else:
        raise AssertionError("Unknown pointer action was accepted")
