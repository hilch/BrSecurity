/*
	BrSecurity
	Security Functions for B&R Automation Studio
	https://github.com/hilch/BrSecurity
*/


#ifndef ARC4RANDOM_H_INCLUDED
#define ARC4RANDOM_H_INCLUDED

#include <stddef.h>

extern const char * const copyright_message[];

void arc4random_buf(void *buf, size_t nbytes);
void arc4random_init(void);
void explicit_bzero(void *b, size_t len);
void copyright(void);


#endif // ARC4RANDOM_H_INCLUDED
