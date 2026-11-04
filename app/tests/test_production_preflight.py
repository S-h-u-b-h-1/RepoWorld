from scripts.check_production import check_config


def test_production_preflight_rejects_local_host():
    found=check_config({'APP_BASE_URL':'http://127.0.0.1:8004','APP_ENV':'development',
                        'REPOWORLD_DB_PATH':'./.data/repoworld.sqlite3'})
    assert any(not ready for _,ready,_ in found)


def test_production_preflight_accepts_complete_config_but_does_not_contact_providers():
    found=check_config({'APP_BASE_URL':'https://repo.example.org','APP_ENV':'production',
                        'REPOWORLD_DB_PATH':'/var/data/repoworld.sqlite3','BHARATCODE_API_KEY':'hidden',
                        'REPOWORLD_REQUIRE_MOUNTED_DB':'1',
                        })
    assert all(ready for _,ready,_ in found)
