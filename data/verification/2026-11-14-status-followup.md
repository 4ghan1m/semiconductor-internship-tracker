# 招聘状态专项复核｜2026-11-14

本次只核查原北京 A/B 六条岗位的招聘状态，专业资格暂不作为判断依据。未登录或实际提交简历。

## 新确认：奔驰电芯研发 219928

- 企业招聘系统 [职位详情](https://career.mercedes-benz.com.cn/recruiting/company/13687/job/219928/job-detail) 对应 ID 219928；同站只读详情接口 `/django_rest/job-detail/info/219928/?job_id=219928&company_id=13687` 返回 HTTP 200、职位 ID 219928、根公司 ID 13687，职位短 ID 为 efDFCX8yS。
- 使用企业页面脚本实际调用的只读 [申请状态接口](https://career.mercedes-benz.com.cn/django_rest/job-detail/apply-status/?short_id=efDFCX8yS&refer_id=) 返回 HTTP 200、code 200、`show_apply: 1`。页面代码用此字段控制申请按钮显示。
- 结论：企业招聘系统显示申请入口，具备当前公开招聘证据；未登录或提交，无法保证最终成功或尚有名额。此前同日补充记录中该岗位官方状态未确认的结论，由本次证据更新。

## 其余五条

1. 同方可靠性 4481409565：[领英同编号页面](https://cn.linkedin.com/jobs/view/%E5%8F%AF%E9%9D%A0%E6%80%A7%E5%AE%9E%E4%B9%A0%E7%94%9F-at-beijing-tongfang-microelectronics-company-4481409565)展示申请按钮，登录后才能继续；招聘网站显示申请入口，未验证实际提交及企业状态。
2. 北汽 AI 新材料 4483402600：[领英同编号页面](https://cn.linkedin.com/jobs/view/ai%E6%96%B0%E6%9D%90%E6%96%99%E8%AE%BE%E8%AE%A1%E5%B7%A5%E7%A8%8B%E5%B8%88%EF%BC%88%E5%AE%9E%E4%B9%A0%EF%BC%89-at-%E5%8C%97%E4%BA%AC%E6%B1%BD%E8%BD%A6%E7%A0%94%E7%A9%B6%E6%80%BB%E9%99%A2%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8-4483402600)展示申请按钮，登录后才能继续；页面为缓存抓取，不证明实时提交及企业状态。
3. 科意设备实习：[高校职位页](https://career.hebut.edu.cn/correcruit/content/id/80926.html)仍有投递指引，发布于2026-09-20；不能验证企业仍接收申请。
4. 北方华创 PE J15415：[智联搜索列表](https://www.zhaopin.com/zhaopin/851bacaed13b41eb83e71c356b03f985/)和此前鱼泡聚合信息展示同编号；未取得具体职位可用申请状态，搜索页面可能滞后。
5. 北方华创 PIE J14086：[鱼泡聚合页](https://m.yupao.com/y/389813681.html)列同编号和联系入口；无法确认企业仍接收、也未核实拨号后状态。

本次重新获得本机网络权限并直接调用奔驰后台；未将登录墙、聚合列表、访问失败当成关闭。未更改 registry、页面和自动任务；本文件是增量证据，账本状态仍需单独刷新。
