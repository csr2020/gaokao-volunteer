on run
	set projectDir to "/Users/csr/Documents/codex/20240422/gaokao-volunteer"
	set healthURL to "http://127.0.0.1:8000/api/health"
	set pageURL to "http://127.0.0.1:8000/"
	
	try
		do shell script "/usr/bin/curl -fsS --max-time 1 " & quoted form of healthURL
	on error
		do shell script "cd " & quoted form of projectDir & " && /usr/bin/nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/gaokao-volunteer.log 2>&1 &"
		repeat 20 times
			delay 0.25
			try
				do shell script "/usr/bin/curl -fsS --max-time 1 " & quoted form of healthURL
				exit repeat
			end try
		end repeat
	end try
	
	open location pageURL
end run
