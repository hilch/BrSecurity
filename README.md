[![License](https://img.shields.io/badge/License-BSD%204--Clause-blue.svg)](https://opensource.org/licenses/BSD-4-Clause) 

# BrSecurity
Security Functions for B&amp;R Automation Studio

---
## Functions

### SecGenPwdHash
implements [bcrypt](https://en.wikipedia.org/wiki/Bcrypt) password hashing (origin: Open BSD) 

You can check the hash online at [https://bcrypt-generator.com](https://bcrypt-generator.com/) or with [Bcrypt.cpp)(https://github.com/hilch/Bcrypt.cpp) in your own program.

### SecValidatePwd
validates user's password against stored hash
```
PROGRAM _CYCLIC

	IF( generate_hash )THEN	
		result_password_hash := SecGenPwdHash( password, 10, password_hash );
		password := '';  (* never store password directly !! *)
		generate_hash := FALSE;
	END_IF


	password_is_valid := SecValidatePwd( password, password_hash );
  
END_PROGRAM
```



---

## License
to comply with the copyright requirements, the library writes to the logbook the first time functions are called.


