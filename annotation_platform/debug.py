from sqlalchemy import create_engine

url = "postgresql://postgres.nsozctktfylscrkjfzrc:ZBGcux3Kw*.*L&q@aws-1-us-east-2.pooler.supabase.com:6543/postgres"

print("start")

print("url =", url)

try:
    engine = create_engine(
        url,
        connect_args={
            "connect_timeout": 10
        }
    )

    print("connecting...")

    conn = engine.connect()

    print("SUCCESS")

except Exception as e:
    print("ERROR:")
    print(e)