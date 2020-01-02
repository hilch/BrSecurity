(********************************************************************
 * COPYRIGHT --  
 ********************************************************************
 * Programm: Passwd
 * Datei: PasswdCyclic.st
 * Autor: github.com/hilch
 ********************************************************************)
PROGRAM _INIT
END_PROGRAM
	
PROGRAM _CYCLIC

	IF( generate_hash )THEN	
		result_password_hash := SecGenPwdHash( password, 10, password_hash );
		password := '';  (* never store password directly !! *)
		generate_hash := FALSE;
	END_IF


	password_is_valid := SecValidatePwd( password, password_hash );
END_PROGRAM
