import coverage

import phd_flow

# ensures coverage is also collected for subprocesses
coverage.process_startup()
phd_flow.run_main("test.test_package")
