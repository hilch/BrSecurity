
PROGRAM _INIT
	brsstrcpy( ADR(data), ADR('Lorem ipsum dolor sit amet, consetetur sadipscing elitr') );
	SecBlfInit_0( key := 'top_secret' );	
	
END_PROGRAM

PROGRAM _CYCLIC
	IF( encode ) THEN
		encode := FALSE;		
		SecBlfEncrypt( SecBlfInit_0.ctx, ADR(data), brsstrlen(ADR(data)) );
	END_IF
	
	IF( decode ) THEN
		decode := FALSE;
		SecBlfDecrypt( SecBlfInit_0.ctx, ADR(data), brsstrlen(ADR(data)) );		
	END_IF
	 
END_PROGRAM
