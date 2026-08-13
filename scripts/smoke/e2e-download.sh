#!/bin/bash
# 下載 arXiv 3 頁論文 PDF 並確認頁數
mkdir -p /tmp/paperkit-e2e
curl -sL -o /tmp/paperkit-e2e/bose-hubbard.pdf "https://arxiv.org/pdf/1010.2688v1"
ls -la /tmp/paperkit-e2e/
file /tmp/paperkit-e2e/bose-hubbard.pdf
