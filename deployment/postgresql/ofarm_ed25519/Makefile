EXTENSION = ofarm_ed25519
MODULE_big = ofarm_ed25519
OBJS = ofarm_ed25519.o ofarm_ed25519_core.o
DATA = ofarm_ed25519--1.0.sql
PGFILEDESC = "ofarm_ed25519 - OFARM verification-only Ed25519 primitive"

SODIUM_PREFIX ?= /opt/ofarm-libsodium
OFARM_TEST_CPPFLAGS ?=
OFARM_EXTRA_CFLAGS ?=
OFARM_EXTRA_LDFLAGS ?=
PG_CPPFLAGS += -I$(SODIUM_PREFIX)/include -fvisibility=hidden $(OFARM_TEST_CPPFLAGS)
PG_CFLAGS += $(OFARM_EXTRA_CFLAGS)
SHLIB_LINK += $(SODIUM_PREFIX)/lib/libsodium.a
LDFLAGS_SL += -Wl,--version-script=$(CURDIR)/ofarm_ed25519.exports $(OFARM_EXTRA_LDFLAGS)

PG_CONFIG ?= pg_config
PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)
