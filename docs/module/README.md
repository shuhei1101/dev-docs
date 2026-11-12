# module

クラス / 関数 / 定数をドメイン分類でまとめる（単体テストの元）

## 目次

<!-- table: data -->

| ページ | 概要 |
| --- | --- |
| [画面 / index.css](./MOD-155-50.css.yaml) | 画面全体の CSS と mdmark の本文への上書き |
| [画面 / アプリとルート](./MOD-155-75.yaml) | 入口・プロバイダ・ルーター・ルートの構成 |
| [画面 / アプリとルート / $source/$.tsx](./MOD-155-52.tsx.yaml) | `/{配信元の ID}/{文書のパス}` のルート |
| [画面 / アプリとルート / $source/index.tsx](./MOD-155-53.tsx.yaml) | `/{配信元の ID}` のルート |
| [画面 / アプリとルート / [_]settings.tsx](./MOD-155-54.tsx.yaml) | `/_settings` のルート |
| [画面 / アプリとルート / __root.tsx](./MOD-155-55.tsx.yaml) | 全てのルートの親。どのルートにも当たらない URL と描画の例外を受ける |
| [画面 / アプリとルート / confirm-dialog.tsx](./MOD-155-1.tsx.yaml) | 画面共通の確認のダイアログと、それを開くフック |
| [画面 / アプリとルート / error-fallback.tsx](./MOD-155-2.tsx.yaml) | 描画中の例外の表示 |
| [画面 / アプリとルート / index.tsx](./MOD-155-56.tsx.yaml) | `/` を開いたときの振り分け |
| [画面 / アプリとルート / initial-loading.tsx](./MOD-155-3.tsx.yaml) | 最初の画面の読み込みが長いときだけ出す読み込み中の表示 |
| [画面 / アプリとルート / main.tsx](./MOD-155-51.tsx.yaml) | SPA の入口。ルーターと Provider を組んで `#root` に描く |
| [画面 / アプリとルート / pending.ts](./MOD-155-4.ts.yaml) | 読み込み中の表示を出すまでの待ち時間 |
| [画面 / アプリとルート / providers.tsx](./MOD-155-5.tsx.yaml) | 画面全体の Provider |
| [画面 / アプリとルート / query-client.ts](./MOD-155-6.ts.yaml) | TanStack Query の QueryClient の既定 |
| [画面 / アプリとルート / router.tsx](./MOD-155-7.tsx.yaml) | TanStack Router のルーターとルートの文脈 |
| [画面 / 共通](./MOD-155-76.yaml) | 画面の間で共通に使う型・エラー・API のクライアント・フック・ストア・部品と、テストの MSW のハンドラ |
| [画面 / 共通 / api-client.ts](./MOD-155-57.ts.yaml) | orval が生成した API の関数が通る fetch の mutator |
| [画面 / 共通 / app-error.ts](./MOD-155-61.ts.yaml) | 画面の API の problem+json を受ける例外の階層 |
| [画面 / 共通 / format.ts](./MOD-155-69.ts.yaml) | 画面に出す日時の書式 |
| [画面 / 共通 / handle-app-error.ts](./MOD-155-62.ts.yaml) | 拾った例外を通知とログに振り分ける |
| [画面 / 共通 / handlers.ts](./MOD-155-73.ts.yaml) | 単体テスト・結合テスト・Storybook が使う MSW のハンドラ |
| [画面 / 共通 / last-doc.ts](./MOD-155-71.ts.yaml) | 設定画面から戻る直前の文書 |
| [画面 / 共通 / logger.ts](./MOD-155-70.ts.yaml) | ブラウザのコンソールへ JSON Lines で書くロガー |
| [画面 / 共通 / preferences.ts](./MOD-155-72.ts.yaml) | 明暗・1 文字のショートカットの設定 |
| [画面 / 共通 / schema.ts](./MOD-155-63.ts.yaml) | orval が生成しない zod のスキーマ |
| [画面 / 共通 / setup-tests.ts](./MOD-155-74.ts.yaml) | 単体テストの共通の準備 |
| [画面 / 共通 / shortcut-dialog.tsx](./MOD-155-58.tsx.yaml) | `?` で開くショートカットの一覧 |
| [画面 / 共通 / shortcuts.ts](./MOD-155-64.ts.yaml) | キーボードのショートカットの定義 |
| [画面 / 共通 / skip-link.tsx](./MOD-155-59.tsx.yaml) | 本文の領域へフォーカスを移すリンク |
| [画面 / 共通 / topbar.tsx](./MOD-155-60.tsx.yaml) | 3 画面に共通のトップバー |
| [画面 / 共通 / use-active-heading.ts](./MOD-155-65.ts.yaml) | 画面の一番上にある見出しを追うフック |
| [画面 / 共通 / use-delayed-flag.ts](./MOD-155-66.ts.yaml) | 待ちが続いたときだけ true にするフック |
| [画面 / 共通 / use-media-query.ts](./MOD-155-67.ts.yaml) | メディアクエリに今当たっているかを返すフック |
| [画面 / 共通 / use-shortcut.ts](./MOD-155-68.ts.yaml) | ショートカットの定義の ID でキーを受けるフック |
| [画面 / 文書の画面](./MOD-155-77.yaml) | 文書の画面・見つからない画面と、両方が使う検索・コメントの構成 |
| [画面 / 文書の画面 / comment-format.ts](./MOD-155-34.ts.yaml) | 選んだコメントのコピーの本文と、Issue の作成画面の URL |
| [画面 / 文書の画面 / comment-panel.tsx](./MOD-155-35.tsx.yaml) | 溜めたコメントの一覧と、コピー・起票 |
| [画面 / 文書の画面 / comment-store.ts](./MOD-155-36.ts.yaml) | このブラウザのタブで溜めたコメントの置き場所 |
| [画面 / 文書の画面 / conversion-error-alert.tsx](./MOD-155-8.tsx.yaml) | 本文の代わりに出す変換の失敗 |
| [画面 / 文書の画面 / diff-banner.tsx](./MOD-155-9.tsx.yaml) | 差分の強調と、比べている 2 つのリビジョンの案内 |
| [画面 / 文書の画面 / doc-body.tsx](./MOD-155-10.tsx.yaml) | mdmark で描く文書の本文 |
| [画面 / 文書の画面 / doc-breadcrumb.tsx](./MOD-155-11.tsx.yaml) | 開いている文書の階層のパンくず |
| [画面 / 文書の画面 / doc-header.tsx](./MOD-155-12.tsx.yaml) | 文書のタイトルと情報 |
| [画面 / 文書の画面 / doc-main.tsx](./MOD-155-13.tsx.yaml) | 文書の画面の本文の領域 |
| [画面 / 文書の画面 / doc-sidebar.tsx](./MOD-155-14.tsx.yaml) | 選んでいるタブの文書の一覧 |
| [画面 / 文書の画面 / doc-skeleton.tsx](./MOD-155-15.tsx.yaml) | 文書の取得を待つ間の読み込み中の表示 |
| [画面 / 文書の画面 / doc-tabs.tsx](./MOD-155-16.tsx.yaml) | 配信元の文書の種類のタブ |
| [画面 / 文書の画面 / doc-toc.tsx](./MOD-155-17.tsx.yaml) | 本文の右の目次 |
| [画面 / 文書の画面 / doc-view-screen.tsx](./MOD-155-20.tsx.yaml) | 文書の画面の最上位 |
| [画面 / 文書の画面 / empty-tab.tsx](./MOD-155-18.tsx.yaml) | 選んだタブに文書が無いことの表示 |
| [画面 / 文書の画面 / highlight.ts](./MOD-155-37.ts.yaml) | 検索の結果の抜粋の一致した箇所を分ける |
| [画面 / 文書の画面 / missing-links.tsx](./MOD-155-30.tsx.yaml) | 次のリンクと配信中の配信元 |
| [画面 / 文書の画面 / missing.ts](./MOD-155-32.ts.yaml) | 404 の `missing` を見つからない画面の文言にする |
| [画面 / 文書の画面 / nav.ts](./MOD-155-26.ts.yaml) | 開いているページ・パンくず・ページのタイトルを引く関数 |
| [画面 / 文書の画面 / not-found-screen.tsx](./MOD-155-33.tsx.yaml) | 見つからない画面 |
| [画面 / 文書の画面 / queries.ts](./MOD-155-27.ts.yaml) | 文書の画面の問い合わせとルートの loader |
| [画面 / 文書の画面 / search-dialog.tsx](./MOD-155-38.tsx.yaml) | 開いている配信元・リビジョンの文書を語で探すダイアログ |
| [画面 / 文書の画面 / search.ts](./MOD-155-28.ts.yaml) | 文書の画面の URL のクエリ |
| [画面 / 文書の画面 / serving-sources.ts](./MOD-155-39.ts.yaml) | 端末の設定の取得から配信中の配信元を取り出す |
| [画面 / 文書の画面 / sidebar-drawer.tsx](./MOD-155-19.tsx.yaml) | 狭い幅で文書の一覧を重ねて出すドロワー |
| [画面 / 文書の画面 / tables.ts](./MOD-155-212.ts.yaml) | 本文の表と表のキーを対にし、隠す列を書き込む関数 |
| [画面 / 文書の画面 / toc.ts](./MOD-155-29.ts.yaml) | 目次と、比較元から変わったセクションを引く関数 |
| [画面 / 文書の画面 / use-column-persistence.ts](./MOD-155-21.ts.yaml) | mdmark の列の表示のメニューで出し入れした列を保存するフック |
| [画面 / 文書の画面 / use-doc-navigation.ts](./MOD-155-22.ts.yaml) | 別の文書・リビジョン・配信元へ移る操作のフック |
| [画面 / 文書の画面 / use-doc-screen-effects.ts](./MOD-155-23.ts.yaml) | タブのタイトルと直前の文書を合わせるフック |
| [画面 / 文書の画面 / use-locating.ts](./MOD-155-24.ts.yaml) | コメントのパネルで場所を選ばれたコメントを持つフック |
| [画面 / 文書の画面 / use-mdmark.ts](./MOD-155-25.ts.yaml) | mdmark の `mount` を React の寿命に合わせて呼ぶフック |
| [画面 / 文書の画面 / use-missing-view.ts](./MOD-155-31.ts.yaml) | 見つからない画面に出す内容を読むフック |
| [画面 / 設定画面](./MOD-155-78.yaml) | 設定画面の構成 |
| [画面 / 設定画面 / form.ts](./MOD-155-45.ts.yaml) | 配信元のダイアログの入力のスキーマと、`sources[]` への反映 |
| [画面 / 設定画面 / problem-errors.ts](./MOD-155-47.ts.yaml) | 422 の `errors[]` をダイアログの項目のエラーに振り分ける |
| [画面 / 設定画面 / queries.ts](./MOD-155-48.ts.yaml) | 端末の設定の保存の mutation |
| [画面 / 設定画面 / settings-screen.tsx](./MOD-155-49.tsx.yaml) | 設定画面 |
| [画面 / 設定画面 / source-delete-dialog.tsx](./MOD-155-40.tsx.yaml) | 削除の確認のダイアログ |
| [画面 / 設定画面 / source-edit-dialog.tsx](./MOD-155-41.tsx.yaml) | 配信元のダイアログ（追加・編集） |
| [画面 / 設定画面 / source-skeleton.tsx](./MOD-155-42.tsx.yaml) | 配信元の一覧の読み込み中の表示 |
| [画面 / 設定画面 / source-table.tsx](./MOD-155-43.tsx.yaml) | 配信元の一覧の表 |
| [画面 / 設定画面 / status-badge.tsx](./MOD-155-44.tsx.yaml) | 配信元の状態のバッジと補足 |
| [画面 / 設定画面 / use-source-form.ts](./MOD-155-46.ts.yaml) | 配信元のダイアログのフォームの状態と保存 |
| [管理用プラグイン / セッション開始のフック / session_start.py](./MOD-155-80.py.yaml) | サーバーが落ちていれば起動する |
| [開発ドキュメントサーバー / project-indexの呼び出し](./MOD-155-213.yaml) | project-index の読み取り API と端末の設定の API の呼び出し |
| [開発ドキュメントサーバー / project-indexの呼び出し / client.py](./MOD-155-215.py.yaml) | project-index の読み取り API と端末の設定の API を制限時間つきで呼び、応答を型にする |
| [開発ドキュメントサーバー / project-indexの呼び出し / types.py](./MOD-155-214.py.yaml) | project-index の読み取り API と端末の設定の API の応答の型 |
| [開発ドキュメントサーバー / プロンプト / render.py](./MOD-155-124.py.yaml) | Jinja2 での部品の描画と変数の値の区切り |
| [開発ドキュメントサーバー / プロンプト / runtime.py](./MOD-155-125.py.yaml) | 起動のときのプロンプトの YAML の読み込み・検査と、注入する文の描画 |
| [開発ドキュメントサーバー / プロンプト / types.py](./MOD-155-126.py.yaml) | プロンプトの YAML のモデル・描画の結果・例外 |
| [開発ドキュメントサーバー / 入口](./MOD-155-193.yaml) | `dev-docs` コマンドの引数の組み立てと main |
| [開発ドキュメントサーバー / 入口 / __init__.py](./MOD-155-81.py.yaml) | インストール済みのパッケージからバージョンを引くときの配布名 |
| [開発ドキュメントサーバー / 入口 / __main__.py](./MOD-155-82.py.yaml) | `dev-docs` コマンドの引数の組み立てと main |
| [開発ドキュメントサーバー / 共通](./MOD-155-194.yaml) | 例外の階層・YAML の読み書き・ハッシュ・パスの正規化・オリジンの確認 |
| [開発ドキュメントサーバー / 共通 / api_model.py](./MOD-155-183.py.yaml) | 画面の API の DTO の基底（キーは camelCase） |
| [開発ドキュメントサーバー / 共通 / errors.py](./MOD-155-184.py.yaml) | `DevDocsError` と、MCP・画面が返すエラーの階層 |
| [開発ドキュメントサーバー / 共通 / files.py](./MOD-155-185.py.yaml) | 一時ファイルからのファイルの置き換え |
| [開発ドキュメントサーバー / 共通 / hashing.py](./MOD-155-186.py.yaml) | 内容のハッシュ（文書のバージョン） |
| [開発ドキュメントサーバー / 共通 / origin.py](./MOD-155-181.py.yaml) | 画面と同じオリジンからの要求かの確認 |
| [開発ドキュメントサーバー / 共通 / paths.py](./MOD-155-187.py.yaml) | パスの正規化 |
| [開発ドキュメントサーバー / 共通 / schema_check.py](./MOD-155-188.py.yaml) | JSON Schema の違反を項目のパスつきの `Violation` にする |
| [開発ドキュメントサーバー / 共通 / version.py](./MOD-155-189.py.yaml) | 動いているプロセスが起動した時点の dev-docs のバージョン |
| [開発ドキュメントサーバー / 共通 / yaml_io.py](./MOD-155-190.py.yaml) | YAML の読み込みと、往復編集の読み書き |
| [開発ドキュメントサーバー / 再起動と更新 / control.py](./MOD-155-116.py.yaml) | 再起動の要求と uvicorn の停止 |
| [開発ドキュメントサーバー / 再起動と更新 / types.py](./MOD-155-117.py.yaml) | 再起動・更新の結果と定数 |
| [開発ドキュメントサーバー / 再起動と更新 / update.py](./MOD-155-118.py.yaml) | `git pull --ff-only`・`uv sync` によるクローンの更新 |
| [開発ドキュメントサーバー / 変換](./MOD-155-195.yaml) | スキーマ駆動の変換と、project-index の `converters[]` の結果の Markdown |
| [開発ドキュメントサーバー / 変換 / decisions.py](./MOD-155-92.py.yaml) | 設計書の `decisions` の検討事項の ID と、検討事項の文書のパスの読み取り |
| [開発ドキュメントサーバー / 変換 / diagrams.py](./MOD-155-93.py.yaml) | `x-diagram` の値と手で書く Mermaid の、mdmark の図の部品か Mermaid への描画 |
| [開発ドキュメントサーバー / 変換 / embed.py](./MOD-155-94.py.yaml) | 埋め込みのマーカーのパスの取り出しと、表への展開 |
| [開発ドキュメントサーバー / 変換 / flow_layout.py](./MOD-155-95.py.yaml) | フロー図の中間データの、mdmark のフロー図の部品の定義への配置 |
| [開発ドキュメントサーバー / 変換 / inline.py](./MOD-155-96.py.yaml) | 文字列の値の中の、図・ファイルツリー・手順・参照・Issue 番号・値の選択肢の書き換え |
| [開発ドキュメントサーバー / 変換 / markdown.py](./MOD-155-97.py.yaml) | スキーマ駆動の文書の Markdown への変換と表の描画 |
| [開発ドキュメントサーバー / 変換 / mermaid.py](./MOD-155-98.py.yaml) | 手で書く Mermaid の `flowchart`・`sequenceDiagram` の読み取り |
| [開発ドキュメントサーバー / 変換 / service.py](./MOD-155-99.py.yaml) | 変換の選択と、表のキーの取り出し |
| [開発ドキュメントサーバー / 変換 / types.py](./MOD-155-100.py.yaml) | 変換の結果・失敗・表し方・図の種類・図の中間データ・描画の文脈の型 |
| [開発ドキュメントサーバー / 変更](./MOD-155-196.yaml) | 文書の取得の差分が使う変わったキーの比べ方 |
| [開発ドキュメントサーバー / 変更 / compare.py](./MOD-155-88.py.yaml) | 変わったキーの比べ方 |
| [開発ドキュメントサーバー / 文書](./MOD-155-199.yaml) | project-index が返した文書の項目の値とエイリアス |
| [開発ドキュメントサーバー / 文書 / aliases.py](./MOD-155-106.py.yaml) | エイリアスのキーの検証と、エイリアスの集め |
| [開発ドキュメントサーバー / 文書 / fields.py](./MOD-155-107.py.yaml) | 項目のパスの分解と、項目の値の取得 |
| [開発ドキュメントサーバー / 文書 / types.py](./MOD-155-112.py.yaml) | エイリアスの型 |
| [開発ドキュメントサーバー / 画面のAPI](./MOD-155-204.yaml) | 文書の取得・画面の検索・リビジョンの一覧・表の列の設定の API（project-index から取得） |
| [開発ドキュメントサーバー / 画面のAPI / columns.py](./MOD-155-158.py.yaml) | 表の列の設定の読み書き |
| [開発ドキュメントサーバー / 画面のAPI / document.py](./MOD-155-159.py.yaml) | 画面の文書の取得と、見つからない項目 |
| [開発ドキュメントサーバー / 画面のAPI / nav.py](./MOD-155-160.py.yaml) | 画面のナビゲーションの組み立てと、変わったページ |
| [開発ドキュメントサーバー / 画面のAPI / paths.py](./MOD-155-161.py.yaml) | 画面のページのパスと、文書のページの特定 |
| [開発ドキュメントサーバー / 画面のAPI / route.py](./MOD-155-162.py.yaml) | 画面の API のルーター（`/_api/sources/{source}/docs`・`search`・`refs`・`columns`） |
| [開発ドキュメントサーバー / 画面のAPI / search.py](./MOD-155-163.py.yaml) | 画面の検索（project-index の検索の結果を画面の形にする） |
| [開発ドキュメントサーバー / 画面のAPI / types.py](./MOD-155-164.py.yaml) | 画面の API の要求と結果の型 |
| [開発ドキュメントサーバー / 端末の設定](./MOD-155-205.yaml) | 端末の設定の検証と読み込み、`sources[]` の取得と保存の依頼 |
| [開発ドキュメントサーバー / 端末の設定 / query.py](./MOD-155-146.py.yaml) | 端末の設定の場所・読み込みと検証・待ち受けのポート |
| [開発ドキュメントサーバー / 端末の設定 / route.py](./MOD-155-147.py.yaml) | 端末の設定のルーター（`GET`・`PUT /_api/settings/sources`） |
| [開発ドキュメントサーバー / 端末の設定 / service.py](./MOD-155-148.py.yaml) | `sources[]` の保存の依頼 |
| [開発ドキュメントサーバー / 端末の設定 / types.py](./MOD-155-149.py.yaml) | 端末の設定と、画面の `sources[]` の要求と結果の型 |
| [開発ドキュメントサーバー / 管理 / render.py](./MOD-155-85.py.yaml) | 管理の MCP の `status` の `format: markdown` の応答の文を組み立てる。値は service.py の結果をそのまま使い、計算しない |
| [開発ドキュメントサーバー / 管理 / service.py](./MOD-155-86.py.yaml) | 管理の MCP の `status` の中身。端末の設定を読み、配信元の状態は project-index から取る |
| [開発ドキュメントサーバー / 管理のMCP](./MOD-155-198.yaml) | 管理の MCP の組み立てと、ツールの結果・エラーの変換 |
| [開発ドキュメントサーバー / 管理のMCP / admin.py](./MOD-155-178.py.yaml) | 管理の MCP の組み立て（ツールの登録） |
| [開発ドキュメントサーバー / 管理のMCP / result.py](./MOD-155-180.py.yaml) | ツールの結果・エラーの変換と、管理の MCP のツール名とプロンプトの ID |
| [開発ドキュメントサーバー / 管理の操作 / types.py](./MOD-155-87.py.yaml) | 管理の MCP の `status` の要求と結果の型 |
| [開発ドキュメントサーバー / 絞り込み](./MOD-155-202.yaml) | `nav` の `auto` の `filter` の条件の確かめと照合 |
| [開発ドキュメントサーバー / 絞り込み / fields.py](./MOD-155-134.py.yaml) | 項目の値・計算項目・使える項目・見出しの行 |
| [開発ドキュメントサーバー / 絞り込み / filters.py](./MOD-155-135.py.yaml) | 条件の木の確かめと照合・正規表現・比べる値の解釈（`nav` の `auto` の `filter`） |
| [開発ドキュメントサーバー / 絞り込み / types.py](./MOD-155-140.py.yaml) | `nav` の `auto` の `filter` の条件の木と、見出しの型 |
| [開発ドキュメントサーバー / 設定の移し替え / service.py](./MOD-155-119.py.yaml) | 対象の決定・当てる手順・バックアップを取った適用と、`sources` の project-index への書き出し |
| [開発ドキュメントサーバー / 設定の移し替え / steps.py](./MOD-155-120.py.yaml) | 手順の読み込みと適用 |
| [開発ドキュメントサーバー / 設定の移し替え / types.py](./MOD-155-121.py.yaml) | 手順・対象・例外・終了コード |
| [開発ドキュメントサーバー / 起動](./MOD-155-207.yaml) | `dev-docs serve`・`dev-docs migrate` の部品の配線と、画面の API・管理の MCP を 1 つにまとめたアプリ |
| [開発ドキュメントサーバー / 起動 / app.py](./MOD-155-175.py.yaml) | ルートと MCP のマウントをまとめたアプリの組み立て |
| [開発ドキュメントサーバー / 起動 / error_handlers.py](./MOD-155-176.py.yaml) | 例外の problem+json への変換 |
| [開発ドキュメントサーバー / 起動 / lifespan.py](./MOD-155-177.py.yaml) | マウントした管理の MCP のセッションの管理と、project-indexの呼び出しを閉じるアプリの寿命 |
| [開発ドキュメントサーバー / 起動 / main.py](./MOD-155-174.py.yaml) | `dev-docs serve`・`dev-docs migrate` の部品の配線と、起動のときの配信元の知らせ |
| [開発ドキュメントサーバー / 起動 / screen.py](./MOD-155-182.py.yaml) | 画面のビルドの配信 |

<!-- /table -->
