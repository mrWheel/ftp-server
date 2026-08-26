#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "ftp_protocol.h"

static void test_paths(void)
{
  char path[FTP_PROTOCOL_PATH_MAX];
  assert(ftp_normalize_path("/", "a//b/../c", path, sizeof(path)));
  assert(!strcmp(path, "/a/c"));
  assert(ftp_normalize_path("/data/inbox", "../../..", path, sizeof(path)));
  assert(!strcmp(path, "/"));
  assert(!ftp_normalize_path("/", "bad\\name", path, sizeof(path)));
}

static void test_parser_framing(void)
{
  char line[FTP_PROTOCOL_LINE_MAX];
  size_t used = 0;
  bool complete;
  bool overflow;
  const char *input = "NOOP\r\nLIST\r\n";
  for (const char *character = input; *character; ++character)
  {
    assert(ftp_parser_feed(line, &used, *character, &complete, &overflow));
    assert(!overflow);
    if (complete && !strcmp(line, "NOOP"))
    {
      used = 0;
    }
    else if (complete)
    {
      assert(!strcmp(line, "LIST"));
      used = 0;
    }
  }
  assert(used == 0);
}

static void test_response_formatting(void)
{
  char response[64];
  assert(ftp_format_response(230, response, sizeof(response), "%s", "Ready") == 11);
  assert(!strcmp(response, "230 Ready\r\n"));
  assert(ftp_format_response(500, response, 8, "%s", "Too long") < 0);
}

int main(void)
{
  test_paths();
  test_parser_framing();
  test_response_formatting();
  puts("ftp_protocol tests passed");
  return 0;
}
