read_model -i NuSMV/temp/test_run/verif.smv 
go
check_ltlspec -P "spec1" -o NuSMV/temp/test_run/spec1_result.txt 
check_ltlspec -P "spec2" -o NuSMV/temp/test_run/spec2_result.txt 
check_ltlspec -P "spec3" -o NuSMV/temp/test_run/spec3_result.txt 
check_ltlspec -P "spec4" -o NuSMV/temp/test_run/spec4_result.txt 
check_ltlspec -P "spec5" -o NuSMV/temp/test_run/spec5_result.txt 
check_ltlspec -P "spec6" -o NuSMV/temp/test_run/spec6_result.txt 
quit