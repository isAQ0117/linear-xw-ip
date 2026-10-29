PYTHON ?= python3

.PHONY: py-test rtl-test stage23-test synthesis-check all-tests demo

py-test:
	$(PYTHON) -m unittest -v test_cycle test_fp32 test_stage1_contract test_stage23

rtl-test:
	sh run_rtl_tb.sh

stage23-test:
	sh run_stage23_tb.sh

synthesis-check:
	$(PYTHON) tools/check_stage23_synthesis.py

all-tests: py-test rtl-test stage23-test

demo:
	$(PYTHON) cycle_model.py --out demo_results
