EXTENSION = ofarm_ed25519
MODULE_big = ofarm_ed25519
OBJS = ofarm_ed25519.o ofarm_ed25519_core.o
DATA = ofarm_ed25519--1.0.sql
PGFILEDESC = "ofarm_ed25519 - OFARM verification-only Ed25519 primitive"

SODIUM_PREFIX ?= /opt/ofarm-libsodium
PG_CPPFLAGS += -I$(SODIUM_PREFIX)/include -fvisibility=hidden
SHLIB_LINK += $(SODIUM_PREFIX)/lib/libsodium.a
LDFLAGS_SL += -Wl,--version-script=$(CURDIR)/ofarm_ed25519.exports

PG_CONFIG ?= pg_config
PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)
