/*
	BrSecurity
	Security Functions for B&R Automation Studio
	https://github.com/hilch/BrSecurity
*/

#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <AsTime.h>
#include <sys_lib.h>
#include "openbsd.h"

const char * const copyright_message[] = {
	"https://github.com/hilch/BrSecurity",
	"OpenBSD: bcrypt.c",
	"Copyright (c) 2014 Ted Unangst <tedu@openbsd.org>",
	"Copyright (c) 1997 Niels Provos <provos@umich.edu",
	"Copyright (c) David Mazieres <dm@lcs.mit.edu>",
	"blowfish.c",
	"Copyright 1997 Niels Provos <provos@physnet.uni-hamburg.de>",
	"Copyright 1993 Bruce Schneier",
	0
	};


void arc4random_buf(void *buf, size_t nbytes)
{
	size_t n;

	for( n = 0; n < nbytes; ++ n)
		((char*)(buf))[n] = rand() %256;
}

void arc4random_init(void)
{
	DATE_AND_TIME dt1;
	DTGetTime_typ get_time;

	get_time.enable = 1;
	DTGetTime(&get_time);
	srand( (unsigned int) dt1 );
}

void  explicit_bzero(void *b, size_t len)
{
	volatile void * dont_optimize = memset( b, 0, len );
	dont_optimize = dont_optimize;
}

void copyright(void)
{
	static BOOL copyright = 0;
	if( !copyright )
	{
		copyright = 1;
		int n = 0;
		while( copyright_message[n] )
		{
			ERRxwarning( 50000, 0, (char*) copyright_message[n++] );
			};
	}
}

