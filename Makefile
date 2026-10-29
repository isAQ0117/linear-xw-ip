PYTHON ?= python3

.PHONY: py-test rtl-test stage23-test stage4-test stage4-py-test stage4-synthesis-check synthesis-check all-tests demo

py-test:
	$(PYTHON) -m unittest -v test_cycle test_fp32 test_stage1_contract test_stage23

rtl-test:
	sh run_rtl_tb.sh

stage23-test:
	sh run_stage23_tb.sh

synthesis-check:
	$(PYTHON) tools/check_stage23_synthesis.py

stage4-py-test:
	$(PYTHON) -m unittest -v test_stage4_numeric

stage4-test:
	sh run_stage4_tb.sh

stage4-synthesis-check:
	$(PYTHON) tools/check_stage4_synthesis.py

all-tests: py-test rtl-test stage23-test stage4-test stage5-test

demo:
	$(PYTHON) cycle_model.py --out demo_results

.PHONY: stage5-test stage5-synthesis-check stage5-audit

stage5-test:
	$(PYTHON) tools/run_stage5_all.py

stage5-synthesis-check:
	$(PYTHON) tools/check_stage5_synthesis.py --map

stage5-audit:
	$(PYTHON) tools/audit_stage5.py
