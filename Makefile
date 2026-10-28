PYTHON ?= python3

.PHONY: py-test rtl-test all-tests demo

py-test:
	$(PYTHON) test_cycle.py
	$(PYTHON) test_fp32.py

rtl-test:
	sh run_rtl_tb.sh

all-tests: py-test rtl-test

demo:
	$(PYTHON) cycle_model.py --out demo_results
