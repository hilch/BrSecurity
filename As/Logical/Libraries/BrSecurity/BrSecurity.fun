(********************************************************************
 * COPYRIGHT --  
 ********************************************************************
 * Library: BrSecurity
 * File: BrSecurity.fun
 * Author: github.com/hilch
 * Created: January 02, 2020
 ********************************************************************
 * Functions and function blocks of library BrSecurity
 ********************************************************************)

FUNCTION_BLOCK SecBlfInit
	VAR_INPUT
		key : {REDUND_UNREPLICABLE} STRING[56]; (*key*)
	END_VAR
	VAR_OUTPUT
		ctx : UDINT; (*pointer to blowfish context*)
	END_VAR
	VAR
		context : ARRAY[0..4168] OF USINT; (*blowfish context*)
	END_VAR
END_FUNCTION_BLOCK

FUNCTION SecBlfEncrypt : USINT
	VAR_INPUT
		ctx : UDINT; (*pointer to blowfish context from SecBlfInit()*)
		data : REFERENCE TO USINT; (*pointer to data*)
		data_len : UDINT; (*length of data*)
	END_VAR
END_FUNCTION

FUNCTION SecBlfDecrypt : USINT
	VAR_INPUT
		ctx : UDINT; (*pointer to blowfish context from SecBlfInit()*)
		data : REFERENCE TO USINT; (*pointer to data*)
		data_len : UDINT; (*length of data*)
	END_VAR
END_FUNCTION

FUNCTION SecGenPwdHash : BOOL (*generate brcypt password hash*) (*$GROUP=User*)
	VAR_INPUT
		password : STRING[56]; (*password input*)
		rounds : USINT; (*rounds input*)
		hash : STRING[60]; (*hash output*)
	END_VAR
END_FUNCTION

FUNCTION SecValidatePwd : BOOL (*Validate bcrypt password hash*) (*$GROUP=User*)
	VAR_INPUT
		password : STRING[56]; (*password input*)
		hash : STRING[60]; (*hash input*)
	END_VAR
END_FUNCTION
