# download_remote_ssh.py
import requests
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def download_remote_ssh():
    """Remote-SSH 확장 프로그램 다운로드"""

    api_url = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json;api-version=7.1-preview.1"
    }

    body = {
        "filters": [{
            "criteria": [
                {"filterType": 7, "value": "ms-vscode-remote.remote-ssh"}
            ]
        }],
        "flags": 914
    }

    try:
        print("확장 프로그램 정보 조회 중...")
        response = requests.post(api_url, json=body, headers=headers, verify=False, timeout=30)
        response.raise_for_status()

        data = response.json()
        ext_data = data["results"][0]["extensions"][0]
        version_data = ext_data["versions"][0]
        version = version_data["version"]

        print(f"최신 버전: {version}")

        # VSIX URL 찾기
        vsix_url = None
        for file_info in version_data["files"]:
            if file_info["assetType"] == "Microsoft.VisualStudio.Services.VSIXPackage":
                vsix_url = file_info["source"]
                break

        if not vsix_url:
            print("다운로드 URL을 찾을 수 없습니다.")
            return False

        # 파일 다운로드
        output_file = f"remote-ssh-{version}.vsix"
        print(f"다운로드 중: {vsix_url}")

        file_response = requests.get(vsix_url, stream=True, verify=False, timeout=300)
        file_response.raise_for_status()

        total_size = int(file_response.headers.get('content-length', 0))
        downloaded = 0

        with open(output_file, "wb") as f:
            for chunk in file_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\r진행률: {progress:.1f}%", end="", flush=True)

        print(f"\n\n다운로드 완료: {output_file}")
        print(f"\n다음 단계:")
        print(f"1. VS Code에서 Ctrl+Shift+P 누르기")
        print(f"2. 'Extensions: Install from VSIX...' 입력")
        print(f"3. 다운로드한 파일 선택: {output_file}")

        return True

    except Exception as e:
        print(f"오류 발생: {e}")
        return False

if __name__ == "__main__":
    download_remote_ssh()