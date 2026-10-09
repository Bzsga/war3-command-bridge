import sys
from pathlib import Path

if __name__ == '__main__':
    if len(sys.argv)>3 and sys.argv[1]=='--demo-build-source':
        Path(sys.argv[3]).write_bytes(Path(sys.argv[2]).read_bytes())
        raise SystemExit(0)
    if len(sys.argv)>3 and sys.argv[1]=='--host-owner':
        from workbench.host_owner import main
        raise SystemExit(main(sys.argv[2],sys.argv[3]))
    if len(sys.argv)>1 and sys.argv[1]=='--worker':
        from workbench.worker import main
        raise SystemExit(main(Path(sys.argv[2])))
    if len(sys.argv)>1 and sys.argv[1]=='--run':
        from workbench.cli import main
        raise SystemExit(main(sys.argv[2:]))
    if len(sys.argv)>2 and sys.argv[1]=='--self-test':
        from workbench.smoke import main
        raise SystemExit(main(sys.argv[2]))
    from workbench.ui import main
    raise SystemExit(main())
