#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>

// HTTP/1.0 requests deliberately require an explicit Content-Length response.
// Bound the complete header section and every line; reject ambiguous framing.
struct GithubHttpHeaders {
  bool complete=false,failed=false,hasLength=false;
  int code=0;
  size_t length=0;
  char location[2049]={};
  bool redirect() const {return code==301 || code==302 || code==303 || code==307 || code==308;}
  void accept(int value) {
    if(complete || failed)return;
    if(++total>16384 || value<=0 || value>127) {failed=true;return;}
    if(value=='\n') {
      if(!used || line[used-1]!='\r'){failed=true;return;}
      line[--used]=0;parse();used=0;return;
    }
    if(used>=sizeof(line)-1) {failed=true;return;}
    line[used++]=value;
  }
 private:
  char line[2080]={};
  size_t used=0,total=0;
  void parse() {
    if(!code) {
      if((strncmp(line,"HTTP/1.0 ",9) && strncmp(line,"HTTP/1.1 ",9)) || strlen(line)<12 ||
        line[9]<'1' || line[9]>'5' || line[10]<'0' || line[10]>'9' || line[11]<'0' || line[11]>'9' ||
        (line[12] && line[12]!=' ')) {failed=true;return;}
      code=(line[9]-'0')*100+(line[10]-'0')*10+line[11]-'0';return;
    }
    if(!*line) {complete=true;return;}
    char *colon=strchr(line,':');if(!colon || colon==line) {failed=true;return;}*colon=0;
    char *value=colon+1;while(*value==' ' || *value=='\t')value++;
    if(!strcasecmp(line,"Transfer-Encoding") || !strcasecmp(line,"Content-Encoding")){failed=true;return;}
    if(!strcasecmp(line,"Location")) {
      if(*location || strlen(value)>=sizeof(location)){failed=true;return;}strcpy(location,value);
    }
    if(!strcasecmp(line,"Content-Length")) {
      if(hasLength || !*value) {failed=true;return;}
      hasLength=true;
      for(const char *p=value;*p;p++) {
        if(*p<'0' || *p>'9' || length>0x300000/10) {failed=true;return;}
        length=length*10+*p-'0';if(length>0x300000){failed=true;return;}
      }
    }
  }
};
