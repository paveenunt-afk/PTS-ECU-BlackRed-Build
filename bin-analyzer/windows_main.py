import sys
from pathlib import Path

def self_test():
    import json
    import tempfile
    from bin_analysis import catalog, inspect, available_architectures
    from pts_analyzer import Analyzer
    assert len(catalog()) == 83
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/"probe.bin"
        path.write_bytes(b"\0"*32+b"38770-K21-901"+b"\0"*32)
        result=inspect(path)
        assert result["embedded_part_candidates"][0]["text"] == "38770-K21-901"
    window=Analyzer()
    window.withdraw()
    window.update()
    window.destroy()
    print(json.dumps({"status":"passed","catalog_rows":83,"gui_constructed":True,"architectures":list(available_architectures()),"hardware_tested":False}))

if __name__ == "__main__":
    if "--flash-engine" in sys.argv:
        sys.argv.remove("--flash-engine")
        from flash_engine import main
        try:
            main()
        except Exception as exc:
            print(f"Stopped: {exc}",flush=True)
            raise SystemExit(1)
    elif "--self-test" in sys.argv:
        self_test()
    else:
        if sys.platform == "win32":
            import ctypes
            handle=ctypes.windll.kernel32.GetConsoleWindow()
            if handle:ctypes.windll.user32.ShowWindow(handle,0)
        from pts_analyzer import Analyzer
        Analyzer().mainloop()
