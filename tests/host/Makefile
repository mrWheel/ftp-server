CC ?= cc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror -D_POSIX_C_SOURCE=200809L

.PHONY: all test clean

all: test_ftp_protocol

test_ftp_protocol: test_ftp_protocol.c ../../components/ftp_server/ftp_protocol.c ../../components/ftp_server/ftp_protocol.h
	$(CC) $(CFLAGS) -I../../components/ftp_server -o $@ test_ftp_protocol.c ../../components/ftp_server/ftp_protocol.c

test: test_ftp_protocol
	./test_ftp_protocol

clean:
	rm -f test_ftp_protocol
