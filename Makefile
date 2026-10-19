PYTHON := python3
CYTHON := cython
CLANG := clang
APP_NAME := build/gumc
BUILD_DIR := build
ZIP_SRCS := Gum
ZIP_FILE := $(BUILD_DIR)/Gum.zip
MAIN_PY := main.py
MAIN_PY_CLANG := temp.py
INSTALL_LOCATION := /usr/local/bin
ARCHS := arm64 x86_64
ARCH_FLAGS := $(foreach arch,$(ARCHS),-arch $(arch))

PYVERSION := $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('LDVERSION') or sysconfig.get_python_version())")
PYINCLUDE := $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_path('include'))")
PYLIBDIR := $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")

.PHONY: all clean ziprebuild run

all: $(APP_NAME)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(MAIN_PY_CLANG): $(MAIN_PY)
	clangver="$$( $(CLANG) --version | head -n 1 | cut -d ' ' -f 4- )"; \
	(head -n 1 $< && echo "clang = '$$clangver'" && tail -n +2 $<) > $@  # This passes in the clang version into main.py

$(BUILD_DIR)/launcher.c: $(MAIN_PY_CLANG) | $(BUILD_DIR)
	$(CYTHON) --embed -3 -o $@ $<

$(ZIP_FILE): $(shell find $(ZIP_SRCS) -type f)
	zip -r $@ $(ZIP_SRCS) -x '**/__pycache__/**'

# Build binary and append ZIP without overwriting in place
$(APP_NAME): $(BUILD_DIR)/launcher.c $(ZIP_FILE)
	$(CLANG) -Os $(ARCH_FLAGS) -I$(PYINCLUDE) $(BUILD_DIR)/launcher.c -o $@.bin \
		-L$(PYLIBDIR) -lpython$(PYVERSION) -pthread -lm -lutil -ldl -ferror-limit=0
	cat $@.bin $(ZIP_FILE) > $@
	rm $@.bin
	chmod u+x $@

run: $(APP_NAME)
	printf '\33c\e[3J\33c'
	./$(APP_NAME) || exit 0

clean:
	rm -rf $(BUILD_DIR) $(APP_NAME) $(MAIN_PY_CLANG)

copy: $(APP_NAME)
	cp build/gumc ~/CLionProjects/Widgies/gumc

$(INSTALL_LOCATION):
	mkdir -p $(INSTALL_LOCATION)

install: $(APP_NAME) $(INSTALL_LOCATION)
	sudo install -m 755 $(APP_NAME) $(INSTALL_LOCATION)/gumc
