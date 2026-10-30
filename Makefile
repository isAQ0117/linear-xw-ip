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

.PHONY: stage6-test stage7-test stage67-fault-test stage67-extended-test stage67-synthesis-check

stage6-test:
	$(PYTHON) tools/run_stage67.py --stage 6

stage7-test:
	$(PYTHON) tools/run_stage67.py --stage 7

stage67-fault-test:
	$(PYTHON) tools/run_stage67.py --stage fault

stage67-extended-test:
	$(PYTHON) tools/run_stage67.py --stage extended

stage67-synthesis-check:
	$(PYTHON) tools/check_stage67_synthesis.py --map

all-tests: stage6-test stage7-test stage67-fault-test stage67-extended-test

.NOTPARALLEL:
.PHONY: stage67-review
stage67-review: stage6-test stage7-test
	$(PYTHON) tools/review_stage67.py
	$(PYTHON) tools/report_stage67.py
	$(PYTHON) tools/audit_stage67.py

all-tests: stage67-review

.PHONY: stage67-retry-test
stage67-retry-test:
	$(PYTHON) tools/run_stage67.py --stage retry

stage67-review: stage67-retry-test stage67-fault-test stage67-extended-test
all-tests: stage67-retry-test
