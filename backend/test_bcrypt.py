import bcrypt
hash_str = "$2b$12$rco3/9qywemUqr93bITjSuU4eeSW.G9AQK9v/rL0L4h8S6.jFh5Ii"
print("Testing hash:", hash_str)
try:
    for pw in ["admin", "Admin", "password", "123456", "Admin@123", "admin123", "Rohit", "rohit", "12345"]:
        if bcrypt.checkpw(pw.encode('utf-8'), hash_str.encode('utf-8')):
            print("FOUND IT: ", pw)
            break
except Exception as e:
    print("Error:", e)
