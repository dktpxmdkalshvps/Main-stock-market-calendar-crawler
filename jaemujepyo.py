import OpenDartReader
import pandas as pd

# 1. API 키 설정 (메일로 받은 키를 꼭 넣어주세요)
api_key = 'e08b49bfc7ba056a74dd0e5af8b919de558a7d51' 
dart = OpenDartReader(api_key)

def get_financial_summary(corp_code, year):
    # finstate 메서드로 데이터 호출
    try:
        df = dart.finstate(corp_code, year, reprt_code='11011')
    except Exception as e:
        print(f"API 호출 중 오류 발생: {e}")
        return None
    
    # API 응답 결과 확인 (인증키 오류 등 체크)
    if df is None or df.empty:
        print(f"데이터를 가져오지 못했습니다. 인증키 활성화 여부나 종목코드를 확인하세요.")
        return None

    # 연결재무제표(CFS) 기준 필터링
    df_filtered = df[df['fs_div'] == 'CFS']
    
    if df_filtered.empty:
        # 연결재무제표가 없는 경우 개별재무제표(OFS) 시도
        df_filtered = df[df['fs_div'] == 'OFS']

    summary = df_filtered[['account_nm', 'thstrm_amount', 'frmtrm_amount']].copy()
    
    # 숫자 변환 및 단위 변경 (억 원)
    for col in ['thstrm_amount', 'frmtrm_amount']:
        summary[col] = pd.to_numeric(summary[col].str.replace(',', ''), errors='coerce')
    
    summary[['thstrm_amount', 'frmtrm_amount']] /= 100_000_000
    summary = summary.rename(columns={
        'thstrm_amount': f'{year}년 (억)',
        'frmtrm_amount': f'{year-1}년 (억)'
    })
    
    return summary.set_index('account_nm')

# 2. 실행 (종목코드 005930 사용)
try:
    # '삼성전자' 대신 종목코드를 넣는 것이 더 정확합니다.
    result = get_financial_summary('005930', 2023)
    
    if result is not None:
        target_accounts = ['매출액', '영업이익', '당기순이익', '자산총계', '부채총계', '자본총계']
        final_view = result.reindex([acc for acc in target_accounts if acc in result.index])
        print("\n[분석 결과]")
        print(final_view)
except Exception as e:
    print(f"프로그램 실행 오류: {e}")