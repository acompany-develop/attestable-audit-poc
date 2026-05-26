ARCH_LIBDIR ?= /lib/$(shell $(CC) -dumpmachine 2>/dev/null || echo x86_64-linux-gnu)
ENTRYPOINT  ?= $(shell readlink -f $(shell command -v python3))

ifeq ($(DEBUG),1)
GRAMINE_LOG_LEVEL = debug
else
GRAMINE_LOG_LEVEL = error
endif

.PHONY: all
all: auditor.manifest.sgx auditor.sig

auditor.manifest: auditor.manifest.template
	gramine-manifest \
		-Dlog_level=$(GRAMINE_LOG_LEVEL) \
		-Darch_libdir=$(ARCH_LIBDIR) \
		-Dentrypoint=$(ENTRYPOINT) \
		$< $@

auditor.manifest.sgx auditor.sig: sgx_sign
	@:

.INTERMEDIATE: sgx_sign
sgx_sign: auditor.manifest auditor.py
	gramine-sgx-sign \
		--manifest auditor.manifest \
		--output auditor.manifest.sgx

.PHONY: clean
clean:
	$(RM) *.token *.sig *.manifest.sgx auditor.manifest
