from subprocess import CompletedProcess

from app.services.remote_control import RemoteControlService


def test_pointer_moves_with_fixed_safe_steps(monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[1:] == ["getdisplaygeometry"]:
            return CompletedProcess(command, 0, stdout="1920 1080\n", stderr="")
        if command[1:] == ["getmouselocation", "--shell"]:
            return CompletedProcess(command, 0, stdout="X=100\nY=100\nSCREEN=0\nWINDOW=1\n", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("app.services.remote_control.subprocess.run", fake_run)
    service = RemoteControlService(command="xdotool", xauthority="")

    service.control_pointer("left")
    service.control_pointer("down")
    service.control_pointer("click")
    service.control_pointer("scroll_up")
    service.control_pointer("scroll_down")

    assert commands == [
        ["xdotool", "getdisplaygeometry"],
        ["xdotool", "getmouselocation", "--shell"],
        ["xdotool", "mousemove", "--sync", "72", "100"],
        ["xdotool", "getdisplaygeometry"],
        ["xdotool", "getmouselocation", "--shell"],
        ["xdotool", "mousemove", "--sync", "100", "128"],
        ["xdotool", "click", "1"],
        ["xdotool", "click", "--repeat", "3", "--delay", "20", "4"],
        ["xdotool", "click", "--repeat", "3", "--delay", "20", "5"],
    ]


def test_pointer_is_clamped_to_display_edges(monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[1:] == ["getdisplaygeometry"]:
            return CompletedProcess(command, 0, stdout="1920 1080\n", stderr="")
        if command[1:] == ["getmouselocation", "--shell"]:
            return CompletedProcess(command, 0, stdout="X=1915\nY=1075\nSCREEN=0\nWINDOW=1\n", stderr="")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("app.services.remote_control.subprocess.run", fake_run)
    service = RemoteControlService(command="xdotool", xauthority="")

    service.control_pointer("right")
    service.control_pointer("down")

    assert commands[-1] == ["xdotool", "mousemove", "--sync", "1915", "1079"]
    assert ["xdotool", "mousemove", "--sync", "1919", "1075"] in commands


def test_pointer_rejects_unknown_actions():
    service = RemoteControlService(command="xdotool", xauthority="")

    try:
        service.control_pointer("drag")
    except ValueError as error:
        assert str(error) == "Unsupported pointer action"
    else:
        raise AssertionError("Unknown pointer action was accepted")
