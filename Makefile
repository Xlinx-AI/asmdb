.PHONY: native test bench package
native:
	python3 tools/build_native.py
native-bootstrap:
	python3 tools/build_native.py --bootstrap-if-needed
test:
	PYTHONPATH=. python3 -m unittest discover -s tests -v
bench:
	PYTHONPATH=. python3 benchmarks/bench_rag.py
	python3 tools/render_results.py
package:
	cd .. && zip -r ASMDB.zip asmdb -x 'asmdb/.git/*' 'asmdb/**/__pycache__/*'
