"""Second batch of curated skills (data only; see ``techstack_extra`` for rules).

``many(category, "Name=alias1,alias2; Name2; ...")`` builds case-insensitive rows
for distinctive branded names only. Anything that is also a common word
(flux, ray, mirror, echo, gin, fiber, ...) must NOT be listed here; use ``cs``
with a context lookahead in ``techstack_extra`` style instead.
"""

from __future__ import annotations

import re

from worker.techstack_extra import Spec, cs, ci


# Frozen copy of the one-token names below that are ordinary English words, so the
# result never depends on the build machine's /usr/share/dict.
_COMMON_WORDS = frozenset({
    "anvil",
    "bandit",
    "blackfire",
    "blade",
    "bower",
    "brython",
    "cargo",
    "cesium",
    "clap",
    "coil",
    "convex",
    "credo",
    "devise",
    "elm",
    "embassy",
    "falcon",
    "finagle",
    "flash",
    "flyway",
    "forth",
    "grunt",
    "hack",
    "hangfire",
    "huey",
    "hugo",
    "hypothesis",
    "ignite",
    "leaflet",
    "lit",
    "meteor",
    "mix",
    "ninja",
    "nix",
    "nock",
    "oban",
    "octave",
    "parcel",
    "poco",
    "polka",
    "psalm",
    "pug",
    "quart",
    "ranch",
    "rayon",
    "recoil",
    "refit",
    "responder",
    "rich",
    "scheme",
    "seneca",
    "sequel",
    "snap",
    "swashbuckle",
    "temporal",
    "tox",
    "twisted",
    "undertow",
    "unicorn",
    "verify",
    "absinthe",
    "ada",
    "agenda",
    "anyhow",
    "apollo",
    "apt",
    "architect",
    "arrow",
    "assembler",
    "aurelia",
    "ava",
    "bevy",
    "biome",
    "black",
    "bogus",
    "bolero",
    "boost",
    "bottle",
    "broadway",
    "brunch",
    "bundler",
    "cadence",
    "capybara",
    "chalice",
    "chewy",
    "clang",
    "clarity",
    "click",
    "coherence",
    "connexion",
    "cowboy",
    "criterion",
    "crossbeam",
    "crystal",
    "cue",
    "dash",
    "dialyzer",
    "diesel",
    "doctrine",
    "dylan",
    "elysia",
    "fable",
    "faker",
    "flet",
    "flowable",
    "folly",
    "forever",
    "ginkgo",
    "glassfish",
    "gleam",
    "glide",
    "guava",
    "gulp",
    "guzzle",
    "hermes",
    "huff",
    "husky",
    "hyper",
    "inferno",
    "jackson",
    "jetty",
    "kingfisher",
    "lasso",
    "linaria",
    "liquid",
    "lumen",
    "maple",
    "marko",
    "mechanize",
    "mercury",
    "meson",
    "metal",
    "mezzanine",
    "middleman",
    "mise",
    "mono",
    "moodle",
    "mustache",
    "neon",
    "netty",
    "nim",
    "nitro",
    "orc",
    "orleans",
    "panel",
    "parquet",
    "pascal",
    "passenger",
    "pino",
    "pip",
    "plug",
    "polaris",
    "polly",
    "polymer",
    "premake",
    "pry",
    "puma",
    "pundit",
    "quill",
    "racket",
    "railway",
    "rake",
    "raku",
    "ransack",
    "reactor",
    "realm",
    "rebus",
    "redwood",
    "reflex",
    "relay",
    "rescript",
    "rocket",
    "ruff",
    "rush",
    "sam",
    "scoop",
    "shrine",
    "spectrum",
    "stencil",
    "stimulus",
    "stylus",
    "sway",
    "swiper",
    "tact",
    "tap",
    "textual",
    "thrift",
    "tide",
    "titanium",
    "tonic",
    "tower",
    "tracing",
    "trio",
    "turbo",
    "twig",
    "typer",
    "volta",
    "wagtail",
    "warp",
    "waterline",
    "winston",
    "yew",
})


_STOP = frozenset({"processing", "requests", "responses", "constructs", "intrinsics",
                   "templates", "architect", "panel", "rich", "black", "click", "dash",
                   "analog", "nerves", "waterline", "temporal"})


def _english() -> frozenset[str]:
    return _COMMON_WORDS


def _flex(word: str) -> str:
    return re.escape(word).replace(r"\ ", r"[\s-]?")


_NEVER = r"(?!)"


def _guarded(name: str, aliases: tuple[str, ...], cat: str) -> Spec:
    """Ambiguous one-token names never match as bare words.

    The name is dropped from free-text matching; only disambiguating aliases
    (multi-word or long distinctive ones) match. Short non-word acronyms with
    no alias match case-sensitively exactly as written. Aliases stay valid
    source-tag names either way.
    """
    from worker.techstack import _text_alias

    text = [a for a in aliases if _text_alias(a)]
    if text:
        return (name, cat, aliases, "|".join(_flex(a) for a in text), False)
    if name.lower() in _english() or any(ch.isdigit() for ch in name) and len(name) <= 3:
        return (name, cat, aliases, _NEVER, False)
    return (name, cat, aliases, re.escape(name), True)


def many(cat: str, blob: str) -> list[Spec]:
    rows: list[Spec] = []
    for part in blob.replace("\n", " ").split(";"):
        part = part.strip()
        if not part:
            continue
        name, _, rest = part.partition("=")
        aliases = tuple(a.strip() for a in rest.split(",") if a.strip())
        name = name.strip()
        toks = re.findall(r"[A-Za-z]+", name)
        risky = " " not in name and (
            name.lower() in _english() or len(name) <= 4 or name.lower() in _STOP
        )
        if risky and len(toks) <= 1:
            rows.append(_guarded(name, tuple(a.lower() for a in aliases), cat))
            continue
        rows.append(ci(name, cat, *aliases))
    return rows


SPECS2: list[Spec] = [
    # ---------------- languages & runtimes ----------------
    *many("language", """Elm; Nim=nimlang; Crystal=crystal-lang; Racket; Scheme=scheme lisp; Smalltalk; Pharo; Ada=ada 95; SPARK Ada; D language=dlang;
    Erlang OTP=otp; Gleam; Hack=hacklang; Raku; Tcl; AWK=awk; sed=sed command; Vim script=vimscript; Emacs Lisp=elisp;
    Objective-C++=objc++; Kotlin Native; Kotlin/JS; Scala.js=scalajs; ReScript; PureScript; Reason ML=reasonml; Idris; Agda; Coq; Lean 4=lean4;
    Standard ML=sml; F* language; Mercury; Forth; APL; J language; Q language kdb=kdb+; Pascal=free pascal; Modula-2; Eiffel; Dylan; Io language;
    Groovy Grails=grails; GDScript; Haxe; ActionScript; Flash; Processing=processing language; Wolfram Language=mathematica; Maple; Octave=gnu octave;
    Scilab; SAS Macro; PL/I=pl/1; RPG IV=rpgle; JCL; REXX; Natural ADABAS=adabas; ABAP OO; ABAP CDS; X++; AL language=al extension; PowerBuilder;
    Visual Basic 6=vb6; ASP Classic; ColdFusion=cfml; Lasso; Cobol-85; Assembler=hlasm; MASM; NASM; WebAssembly Text=wat; LLVM IR=llvm; MLIR;
    CUDA C++; OpenCL; OpenMP; MPI=openmpi; Verilog-A; Chisel HDL=chisel; Bluespec; SpinalHDL; Clash HDL; HLS=vitis hls; Cairo language=starknet cairo;
    Move language=aptos move; Sway=sway language; Huff; Yul; FunC=ton func; Tact; Michelson; Plutus; Aiken; Clarity=clarity language; Ink!=ink smart contracts;
    TypeSpec; Protocol Buffers v3; Thrift=apache thrift; Avro=apache avro; Parquet=apache parquet; ORC=orc format; Arrow=apache arrow; MessagePack=msgpack; CBOR; FlatBuffers; Cap'n Proto=capnproto;
    JSON Schema=jsonschema; JSONata; JMESPath; jq=jq tool; XPath; XQuery; XSD; GraphQL SDL; CUE=cuelang; Jsonnet; Dhall; HCL=hashicorp configuration language; Starlark; Nix=nixlang;
    Makefile=gnu make; CMake; Bazel; Buck2; Ninja=ninja build; Meson; Autotools=autoconf; Premake; SCons; Gradle Kotlin DSL=gradle kts; sbt=scala build tool; Leiningen; Cargo=rust cargo; Go Modules=go mod; pip; Conda=anaconda; Poetry Python=python poetry; uv Python=astral uv; Pipenv; Hatch Python; PDM Python; setuptools; tox; nox; virtualenv; pyenv; Nvm=nvm node; Volta; Rustup; SDKMAN=sdkman; asdf=asdf vm; mise=mise-en-place; Homebrew=brew; Chocolatey=choco; Scoop; Winget; apt=apt-get; yum=yum package; dnf; Snap=snapcraft; Flatpak; RPM=rpm package; dpkg"""),
    # ---------------- web frontend ----------------
    *many("frontend", """Lit=lit element; Stencil=stenciljs; Polymer=polymer project; Knockout.js=knockoutjs; Backbone.js=backbonejs; Underscore.js=underscorejs; Lodash=lodash.js; Moment.js=momentjs; Day.js=dayjs; date-fns; Luxon; Axios=axios.js; SWR=swr vercel; Apollo=apollo graphql client; Relay=relay modern; urql; Immer=immer.js; XState; Recoil=recoiljs; Jotai=jotai state; Valtio; Pinia; Vuex; Vue Router; Vuetify; Quasar=quasar framework; Element Plus; Naive UI; PrimeVue; PrimeNG; PrimeReact; NativeBase; Angular CLI; Angular Universal; Angular Signals; RxJS Operators; NgRx Store; Akita; Nx Workspace=nx monorepo; Lerna Monorepo=lerna; Rush=rushjs; Changesets; Semantic Release=semantic-release; Husky; lint-staged; Commitlint; Stylelint; Biome=biomejs; Oxlint; Rome Tools; SWC=swc compiler; Turbopack; Rspack; Snowpack; Parcel=parceljs; Browserify; Grunt=gruntjs; Gulp=gulpjs; Brunch; Bower; JSPM; SystemJS; RequireJS; AMD Modules; CommonJS; ES Modules=esm modules; Import Maps; Web Workers; Service Workers=serviceworker; IndexedDB; Web Storage; WebRTC; WebSocket API; Server-Sent Events=sse; WebXR; WebGPU; Canvas API; SVG; Web Audio API; Web Animations API; Intersection Observer; Shadow DOM; Custom Elements; CSS Grid; Flexbox=css flexbox; CSS Variables=css custom properties; CSS-in-JS; Emotion CSS=emotion css; Stitches; Vanilla Extract; Linaria; PostCSS; Autoprefixer; Less CSS=less.js; Stylus; BEM=bem methodology; SMACSS; OOCSS; Atomic CSS; UnoCSS; Windi CSS=windicss; Bulma; Foundation CSS=zurb foundation; Semantic UI; Materialize CSS; Pure CSS; Tachyons; Open Props; DaisyUI; Headless UI; Ark UI; Park UI; Mantine UI; Evergreen UI; Blueprint JS=blueprintjs; Fluent UI=fluentui; Carbon Design System=carbon design; Atlassian Design System; Polaris=shopify polaris; Spectrum=adobe spectrum; Ionic Framework; Framework7; Onsen UI; Cordova=apache cordova; PhoneGap; Meteor=meteorjs; Sails.js=sailsjs; Marko=markojs; Inferno=infernojs; Mithril=mithriljs; Hyperapp; Riot.js=riotjs; Aurelia; Dojo Toolkit; ExtJS=sencha ext js; GWT=google web toolkit; Vaadin Flow; Blazor WebAssembly; Razor Pages; Thymeleaf; JSP=javaserver pages; JSF=javaserver faces; Freemarker; Velocity Templates; Handlebars=handlebars.js; Mustache; Pug=pugjs; EJS=ejs templates; Nunjucks; Jinja2=jinja; Twig; Blade=laravel blade; Liquid=liquid templates; Jekyll; Hugo=gohugo; Eleventy=11ty; Hexo; Docusaurus Site; VitePress; VuePress; Nextra; Gridsome; Scully; Astro Islands; Fresh Deno=deno fresh; Hono=honojs; Elysia=elysiajs; SolidStart; Analog=analogjs; Redwood=redwoodjs; Blitz.js=blitzjs; Qwik City; Million.js; Preact Signals; React Server Components=rsc; React Suspense; React Hooks; React Context; React Testing Library=rtl; React Hook Form; Formik; Yup; Zod=zod schema; Joi=joi validation; Ajv; Valibot; React Table=tanstack table; React Virtualized=react-window; React DnD; React Spring; React Three Fiber=r3f; Recharts; Chart.js=chartjs; Highcharts; ECharts=apache echarts; Plotly=plotly.js; Victory Charts; Nivo; Leaflet=leafletjs; Mapbox=mapbox gl; OpenLayers; Cesium=cesiumjs; Konva; Fabric.js=fabricjs; PixiJS=pixi.js; Phaser=phaser.io; Babylon.js=babylonjs; A-Frame=aframe; p5.js=p5js; Anime.js=animejs; Lottie Web=lottie-web; Swiper=swiperjs; Slick Carousel; TinyMCE; CKEditor; Quill=quilljs; ProseMirror; Tiptap; Slate.js=slatejs; Draft.js=draftjs; Monaco Editor; CodeMirror; Ace Editor=ace.js"""),
    # ---------------- mobile ----------------
    *many("mobile", """Swift Package Manager=spm; Carthage; Combine Framework=apple combine; SwiftUI Navigation; Core Animation; Core Graphics; Core ML=coreml; Core Location; Core Bluetooth; Metal=apple metal; AVFoundation; HealthKit; StoreKit; CloudKit; WidgetKit; ActivityKit; MapKit; RealityKit; SpriteKit; SceneKit; GameplayKit; UserNotifications; Siri Shortcuts=app intents; Objective-C Runtime; Alamofire; Moya; Kingfisher; SDWebImage; SnapKit; Lottie iOS; Realm=realm db; GRDB; SQLite.swift; Swinject; The Composable Architecture=tca; VIPER architecture=viper; Clean Swift; Dagger Hilt=hilt; Koin=koin di; Kodein; Room Database=android room; DataStore; WorkManager; Navigation Component; LiveData; Android ViewModel; Kotlin Flow; Jetpack Paging; CameraX; ExoPlayer=media3; Glide; Coil; Picasso; OkHttp; Moshi; Gson; Kotlinx Serialization; Compose Multiplatform; Android NDK; JNI; Android SDK; Android Jetpack Libraries; Material Components; Firebase Crashlytics=crashlytics; Firebase Analytics; Firebase Cloud Messaging; Firebase Auth; Firestore=cloud firestore; Firebase Realtime Database; Firebase Remote Config; Firebase Hosting; App Center=visual studio app center; CodePush; Bitrise; Codemagic; Fastlane Match; Gradle Play Publisher; Google Play Console; App Store Connect; TestFlight Beta; Flutter Bloc=flutter_bloc; GetX=flutter getx; Provider Flutter=flutter provider; MobX Flutter; Flutter Hooks; Dio=dio flutter; Flutter Web; Flutter Desktop; Dart FFI; React Native Reanimated=reanimated; React Native Navigation; React Navigation; React Native Gesture Handler; React Native Paper; React Native Web; Expo Router; Expo EAS=eas build; Hermes=hermes engine; Fabric Architecture=react native fabric; TurboModules; Ignite=infinite red ignite; WatermelonDB; MMKV; Realm React Native; Capacitor Plugins; Ionic Angular; Quasar Mobile; NativeScript Vue; Titanium=appcelerator; Corona SDK; Solar2D; Cocos2d-x=cocos2dx; Cocos Creator; LibGDX; Defold; GameMaker=gamemaker studio; Construct 3; RPG Maker; Ren'Py=renpy; Stencyl; Buildbox; MonoGame; FNA; Godot Engine 4; Unity DOTS=dots ecs; Unity ECS; Unity Addressables; Unity Netcode; Unity Cinemachine; Unity Shader Graph; Unity UI Toolkit; Unity Visual Scripting; Unity ML-Agents=ml-agents; Unity Mirror Networking; Unreal Blueprints=ue blueprints; Unreal Niagara; Unreal Lumen; Unreal Nanite; Unreal Gameplay Ability System=gas unreal; Unreal Engine Networking; Unreal MetaHuman; Unreal Sequencer; Epic Online Services=eos; Steamworks; PlayFab; Photon Fusion; Mirror Networking; Nakama; Colyseus; SpatialOS; Agones; AWS GameLift=gamelift; Firebase Games; Unity Gaming Services=ugs; ARCore Geospatial; Vuforia; Niantic Lightship=lightship; 8th Wall; Spark AR; Lens Studio; Wikitude; OpenXR; Oculus SDK=meta quest sdk; SteamVR; Mixed Reality Toolkit=mrtk; Apple Vision Pro=visionos; Magic Leap"""),
    # ---------------- backend ----------------
    *many("backend", """Gin Gonic=gin-gonic; Echo Framework=labstack echo; Fiber Go=gofiber; Chi Router=go-chi; Gorilla Mux=gorilla/mux; Buffalo Go; Beego; Revel Go; GORM; sqlx Go; Ent Go=entgo; Wire Go=google wire; Cobra CLI=spf13 cobra; Viper Config; Testify Go=testify; Ginkgo; Gomega; Spring MVC; Spring WebFlux; Spring Security Framework; Spring Data JPA; Spring Cloud Gateway; Spring Cloud Netflix; Spring Batch; Spring Integration; Spring AI; Spring Native; Spring Shell; Spring Kafka; Spring AMQP; Reactor=project reactor; RxJava; Vavr; Guava=google guava; Apache Commons; Jackson=jackson json; Gson Java; JAXB; JPA Criteria; QueryDSL; jOOQ; MyBatis; Flyway; Liquibase; Hibernate ORM; Hibernate Envers; EclipseLink; OpenJPA; Netty; Undertow; Jetty=eclipse jetty; WildFly=jboss wildfly; JBoss=jboss eap; WebLogic=oracle weblogic; WebSphere=ibm websphere; GlassFish; Payara; Helidon; Javalin; Spark Java=sparkjava; Ratpack; Play Scala; Scalatra; http4s; Cats Effect=cats-effect; ZIO; Akka HTTP; Akka Streams; Lagom; Finagle; Slick Scala=scala slick; Doobie; Scalatest; Specs2; ScalaCheck; Kotlin Exposed=jetbrains exposed; Ktor Server; Http4k; Vert.x Web; Quarkus Reactive; Micronaut Data; Helidon MP; Eclipse MicroProfile=microprofile; Eclipse Vert.x; Camel K; Apache CXF; Apache Axis; Apache Tika; Apache POI; Apache PDFBox; iText=itext pdf; JasperReports=jasper reports; Apache FOP; Apache Velocity; Apache Shiro; Apache Ignite; Apache Geode; Hazelcast; Infinispan; Ehcache; Caffeine Cache; Coherence=oracle coherence; Terracotta; Redisson; Lettuce Redis; Jedis; Spring Session; OAuth2 Proxy; Keycloak Adapter; Django ORM; Django Channels; Django Celery; Django Ninja; Django Rest Framework JWT; Wagtail=wagtail cms; Django CMS; Mezzanine; Pyramid Framework=pylons pyramid; Bottle=bottle.py; CherryPy; Falcon=falcon framework; Sanic; Quart; Litestar; Responder; Hug API; Connexion; Flask-RESTful; Flask-SQLAlchemy; Flask-Login; Flask-Migrate; Marshmallow; Pydantic Settings; Typer=typer cli; Click=click python; argparse; Rich=rich python; Textual=textual tui; Loguru; structlog; Pytest-asyncio; Hypothesis=hypothesis testing python; Factory Boy; Faker; Freezegun; Responses=responses library; VCR.py=vcrpy; Behave BDD; Locust Python; Tox Python; Black=black formatter; Ruff=ruff linter; Flake8; Pylint; mypy; Pyright; isort; Bandit=bandit python; Pre-commit=pre-commit hooks; Sphinx Python; MkDocs Material; Cython; Numba; PyPy; Nuitka; PyInstaller; Briefcase; Kivy; PyQt=pyqt5; PySide; Tkinter; wxPython; Pygame; Pyglet; Arcade Python; Panda3D; Ursina; Streamlit; Gradio; Dash=plotly dash; Panel=holoviz panel; Voila; NiceGUI; Reflex=reflex python; Flet; Anvil; PyScript; Brython; Pyodide; Twisted; Gevent; Eventlet; Trio=trio async; AnyIO; HTTPX; Requests=python requests; urllib3; Selenium Python; Playwright Python; Mechanize; MechanicalSoup; Celery Beat; RQ=python rq; Dramatiq; Huey; Arq; APScheduler; Luigi Pipeline=spotify luigi; Kedro Pipeline; Metaflow; Flyte; ZenML; Prefect Orion; Mage AI=mage.ai; Kestra; Temporal=temporal.io; Cadence=uber cadence; Camunda; Zeebe; Activiti; jBPM; Flowable; Netflix Conductor=conductor oss; Argo Workflows; Tekton Pipelines; Airflow DAGs; Apache Oozie; Azkaban; Rundeck; Control-M=bmc control-m; AutoSys; Stonebranch; Node-RED=nodered; n8n; Zapier; Make.com=integromat; Workato; MuleSoft=mulesoft anypoint; Boomi=dell boomi; TIBCO; WSO2; IBM MQ=websphere mq; IBM ACE=app connect enterprise; SnapLogic; Jitterbit; Informatica Cloud=iics; Talend Cloud; Apache Synapse"""),
    *many("backend", """Express Middleware; Fastify Plugins; Hapi.js=hapijs; Restify; LoopBack=loopback.io; Feathers.js=feathersjs; AdonisJS=adonis; Moleculer; Seneca; Total.js; Polka; Micro Node=zeit micro; Nitro=nitrojs; h3=unjs h3; Nuxt Server; tRPC Server; GraphQL Yoga; Apollo Federation; Hasura; PostGraphile; Prisma Client; Drizzle ORM=drizzle; Knex.js=knexjs; Objection.js=objectionjs; MikroORM; Bookshelf.js; Waterline; Kysely; Slonik; node-postgres=pg node; Bull Queue=bullmq; Agenda=agenda.js; Bee-Queue; Kue; Graphile Worker; pg-boss; Passport.js=passportjs; Helmet.js=helmet node; Morgan Logger; Winston=winston logger; Pino=pino logger; Bunyan; Log4js; Jest Node; Supertest; Nock; Sinon Mock; Chai Assert; AVA=ava test; Tap=node-tap; Playwright Test; Nodemon; PM2; Forever; Cluster Module; Worker Threads; libuv; N-API=node-api; node-gyp; Webpack Node; ts-node; tsx; tsup; SWC Node; esbuild Node; Bun Runtime=bun.sh; Deno Deploy; Cloudflare Workers=workers.dev; Vercel Edge Functions; Netlify Functions; AWS Amplify=amplify; Serverless Framework=serverless.com; SST=sst.dev; Architect=arc.codes; Claudia.js; Zappa; Chalice=aws chalice; SAM=aws sam; Serverless Application Model; LocalStack; Moto=moto mock aws; Pulumi AWS; CDK for Terraform=cdktf; CDK8s; Projen; Constructs; Laravel Eloquent=eloquent orm; Laravel Nova; Laravel Horizon; Laravel Sanctum; Laravel Passport; Laravel Livewire; Laravel Inertia=inertiajs; Laravel Forge; Laravel Vapor; Laravel Octane; Laravel Telescope; Laravel Dusk; Pest PHP=pestphp; Codeception; Behat; PHPStan; Psalm=psalm php; PHP-CS-Fixer; Rector PHP; Composer PHP=composer; Packagist; Slim Framework=slim php; Lumen; Phalcon; FuelPHP; Zend Framework=laminas; Symfony Messenger; Symfony Console; Symfony Flex; Twig Templates; Doctrine=doctrine orm; Propel; RedBeanPHP; ReactPHP; Swoole; RoadRunner; Amp PHP=amphp; Workerman; OpenSwoole; Guzzle; Monolog; PHP-FPM; OPcache; Xdebug; Blackfire; PrestaShop; OpenCart; WooCommerce; Magento 2; Shopware; Sylius; BigCommerce; Craft CMS; Statamic; Concrete CMS=concrete5; TYPO3; MODX; October CMS; Backdrop CMS; Moodle; Mautic; SuiteCRM; Akeneo; Pimcore; ProcessWire; Contao; Grav CMS=grav; WordPress Gutenberg=gutenberg; Elementor; WPBakery; Divi Builder=divi; Advanced Custom Fields=acf; WP-CLI; Roots Sage=sage wordpress; Timber Twig; WP REST API; WooCommerce REST API; Headless WordPress=wpgraphql; Ghost CMS=ghost.org; Strapi CMS; Directus; Payload CMS=payloadcms; KeystoneJS=keystone 6; Sanity.io=sanity studio; Contentful CMS; Prismic; Storyblok; DatoCMS; Hygraph=graphcms; Builder.io; Netlify CMS=decap cms; TinaCMS; Ruby Sinatra; Hanami; Roda; Grape API=ruby grape; Padrino; Rack Middleware=rack; Puma; Unicorn=unicorn server; Passenger=phusion passenger; Thin Server; ActiveRecord; ActiveJob; ActionCable; ActionMailer; ActiveStorage; Hotwire; Turbo=hotwire turbo; Stimulus=stimulus.js; ViewComponent; Devise=devise gem; Pundit; CanCanCan; Sorbet=sorbet typechecker; RuboCop; Minitest; Capybara; FactoryBot; VCR Ruby; WebMock; Faker Ruby; Resque; Delayed Job=delayed_job; GoodJob; Shoryuken; Kaminari; Pagy; Paperclip; CarrierWave; Shrine=shrine.rb; Ransack; Searchkick; Chewy=chewy gem; Elasticsearch Rails; Dry-rb=dry-rb; Trailblazer; Sequel=sequel orm; ROM-rb; Jekyll Ruby; Middleman; Nokogiri; Mechanize Ruby; Bundler; RubyGems; rbenv; RVM=ruby version manager; Capistrano; Chef Ruby; Rake=rake tasks; Thor CLI; Pry; Phoenix LiveView; Ecto=ecto elixir; Plug=plug elixir; Absinthe; Oban; Broadway=broadway elixir; Nerves=nerves project; Livebook; Elixir OTP; GenServer; Mix=mix elixir; ExUnit; Credo; Dialyzer; Bandit Elixir; Cowboy=cowboy erlang; Rebar3; Ranch; Mnesia; ejabberd; RabbitMQ Erlang; Riak; Cowboy WebSocket; Axum=axum rust; Actix Web; Rocket=rocket.rs; Warp=warp rust; Tide=tide rust; Hyper=hyper rust; Tonic=tonic grpc; Tower=tower rust; Serde=serde rust; Diesel=diesel orm; SeaORM; SQLx=sqlx rust; Tokio Runtime; async-std; Rayon; Crossbeam; Clap=clap rust; Tracing=tracing rust; Anyhow; Thiserror; Tauri Rust; Yew=yew rust; Leptos; Dioxus; Bevy=bevy engine; Wasm-bindgen=wasm-bindgen; wasm-pack; Cargo Workspaces; Clippy; Rustfmt; Miri; Cargo-fuzz; Criterion=criterion rust; Proptest; Embassy=embassy rust; RTIC; Rust Embedded=embedded-hal; Zig Build; Boost=boost c++; Qt=qt framework; QML; Qt Quick; Qt Creator; wxWidgets; GTK=gtk+; GTKmm; FLTK; Dear ImGui=imgui; SDL=sdl2; SFML; Poco=poco c++; Abseil=absl; Folly; gRPC C++; Protobuf C++; Eigen=eigen c++; OpenCV C++; PCL=point cloud library; ROS C++; GoogleTest=gtest; Catch2; Boost.Test; CppUnit; Google Benchmark; Valgrind; GDB=gnu gdb; LLDB; AddressSanitizer=asan; UBSan; ThreadSanitizer=tsan; Clang=clang compiler; GCC=gnu gcc; MSVC; Clang-Tidy; Cppcheck; CMake Presets; Conan=conan package manager; vcpkg; Hunter CMake; C++20; C++17; C++14; C++11; Modern C++; STL=c++ stl; Templates C++; SIMD=avx simd; Intrinsics; pthreads; POSIX; Win32 API=winapi; COM=component object model; MFC=microsoft foundation classes; ATL; WinRT; UWP=universal windows platform; WinUI; WPF XAML=xaml; Avalonia; Uno Platform; .NET MAUI Blazor; WinForms Legacy; ASP.NET Core Web API; ASP.NET MVC; ASP.NET Web Forms; Minimal APIs; gRPC .NET; SignalR Core; Orleans=microsoft orleans; Dapr=dapr.io; MassTransit; NServiceBus; Rebus; Hangfire; Quartz.NET=quartznet; Polly=polly resilience; Serilog; NLog; Log4net; AutoMapper; FluentValidation; Newtonsoft.Json=json.net; System.Text.Json; Dapper ORM; NHibernate; LINQ to SQL; OData; Swashbuckle; NSwag; Refit; RestSharp; HttpClient; IdentityServer=duende identityserver; ASP.NET Identity; Entity Framework Core Migrations; xUnit.net; Moq; NSubstitute; FakeItEasy; Bogus; Testcontainers; WireMock; Verify=verify snapshot; BenchmarkDotNet; Roslyn; Source Generators; MSBuild; NuGet Packages; Paket; Cake Build=cakebuild; NUKE Build; FAKE F#=fake build; Giraffe F#; Saturn F#; Fable; Elmish; Bolero; Akka.NET=akkadotnet; Unity C#; Mono; IL2CPP; Xamarin.Forms; Prism Library=prismlib; ReactiveUI; MVVM Toolkit=community toolkit mvvm; CommunityToolkit; SkiaSharp; Uno WebAssembly"""),
    # ---------------- cloud ----------------
    *many("cloud", """AWS Lambda@Edge; AWS Fargate; AWS Batch; AWS Lightsail; AWS Elastic Beanstalk=elastic beanstalk; AWS App Runner; AWS Copilot; AWS ECR=amazon ecr; AWS EKS Anywhere; AWS Outposts; AWS Wavelength; AWS Local Zones; AWS Direct Connect; AWS Transit Gateway; AWS PrivateLink; AWS VPN; AWS Global Accelerator; AWS WAF; AWS Shield; AWS Firewall Manager; AWS Network Firewall; AWS GuardDuty=guardduty; AWS Inspector; AWS Macie; AWS Security Hub=security hub; AWS Detective; AWS Config; AWS CloudTrail=cloudtrail; AWS Organizations; AWS Control Tower; AWS SSO=iam identity center; AWS KMS=amazon kms; AWS Secrets Manager=secrets manager; AWS Systems Manager=ssm parameter store; AWS Certificate Manager=acm; AWS Artifact; AWS Audit Manager; AWS Backup; AWS DataSync; AWS Transfer Family; AWS Storage Gateway; Amazon EBS=ebs volumes; Amazon EFS; Amazon FSx; Amazon S3 Glacier=glacier; Amazon S3 Select; Amazon Aurora Serverless; Amazon DynamoDB Streams; Amazon DocumentDB=documentdb; Amazon Neptune=neptune graph; Amazon Keyspaces; Amazon Timestream; Amazon QLDB; Amazon MemoryDB; Amazon ElastiCache=elasticache; Amazon OpenSearch Service; Amazon CloudSearch; Amazon Redshift Spectrum; Amazon EMR=elastic mapreduce; Amazon MSK=managed streaming for kafka; Amazon Kinesis Data Streams; Amazon Kinesis Firehose=firehose; Amazon Kinesis Analytics; Amazon QuickSight=quicksight; Amazon Lake Formation=lake formation; AWS Data Pipeline; AWS DMS=database migration service; AWS Schema Conversion Tool; Amazon MQ; Amazon SNS; Amazon EventBridge=eventbridge; Amazon AppSync=appsync; Amazon API Gateway; Amazon SES=simple email service; Amazon Pinpoint; Amazon Connect; Amazon Chime; Amazon WorkSpaces=workspaces; Amazon AppStream; Amazon Cognito Identity; Amazon Rekognition=rekognition; Amazon Textract=textract; Amazon Comprehend=comprehend; Amazon Transcribe=transcribe aws; Amazon Polly; Amazon Lex; Amazon Translate; Amazon Forecast; Amazon Personalize; Amazon Kendra; Amazon Fraud Detector; Amazon Lookout; Amazon Q; Amazon Bedrock Agents; Amazon Titan; Amazon CodeWhisperer; AWS CodeBuild=codebuild; AWS CodeDeploy=codedeploy; AWS CodePipeline=codepipeline; AWS CodeCommit=codecommit; AWS CodeArtifact; AWS Cloud9; AWS X-Ray=xray tracing; AWS AppConfig; AWS Proton; AWS Service Catalog; AWS CloudFormation StackSets; AWS OpsWorks; AWS Trusted Advisor; AWS Well-Architected=well-architected framework; AWS Cost Explorer; AWS Budgets; AWS IoT Core=iot core; AWS IoT Greengrass=greengrass; AWS IoT Analytics; AWS RoboMaker; AWS Ground Station; AWS Snowball=snow family; AWS Mainframe Modernization; AWS Migration Hub; AWS Application Migration Service; AWS Elastic Disaster Recovery; AWS Nitro; AWS Graviton=graviton; AWS Trainium; AWS Inferentia; AWS Marketplace; AWS Amplify Hosting; AWS Device Farm; AWS Lambda Layers; AWS Lambda Powertools=powertools lambda; AWS SDK; AWS CLI=aws cli; Boto3=boto3; AWS Solutions Architect Associate=saa-c03; AWS Developer Associate; AWS SysOps Administrator; AWS DevOps Professional; AWS Certified Cloud Practitioner=cloud practitioner; AWS Security Specialty; AWS Data Analytics Specialty; AWS Machine Learning Specialty; Azure App Service=app service; Azure Container Apps; Azure Container Instances=aci; Azure Container Registry=acr; Azure Kubernetes Service; Azure Arc; Azure Stack; Azure Virtual Machines=azure vm; Azure VM Scale Sets=vmss; Azure Batch; Azure Service Fabric=service fabric; Azure Static Web Apps; Azure Logic Apps=logic apps; Azure API Management=apim; Azure Event Grid=event grid; Azure Event Hubs=event hubs; Azure Notification Hubs; Azure SignalR Service; Azure Relay; Azure Storage=blob storage; Azure Blob Storage; Azure Data Lake Storage=adls; Azure Files; Azure Queue Storage; Azure Table Storage; Azure SQL Database=azure sql; Azure SQL Managed Instance; Azure Database for PostgreSQL; Azure Database for MySQL; Azure Cache for Redis; Azure Cosmos DB for NoSQL; Azure Databricks; Azure HDInsight=hdinsight; Azure Stream Analytics; Azure Data Explorer=kusto; KQL=kusto query language; Azure Purview=microsoft purview; Azure Analysis Services; Azure Data Share; Azure Monitor; Azure Application Insights=application insights; Azure Log Analytics=log analytics; Azure Sentinel SIEM; Azure Security Center=defender for cloud; Azure Key Vault=key vault; Azure Policy; Azure Blueprints; Azure Resource Manager=arm templates; Bicep=azure bicep; Azure CLI=az cli; Azure PowerShell; Azure Automation; Azure Lighthouse; Azure Cost Management; Azure Advisor; Azure Front Door=front door; Azure Application Gateway; Azure Load Balancer; Azure Traffic Manager; Azure Firewall; Azure DDoS Protection; Azure Bastion; Azure ExpressRoute=expressroute; Azure VPN Gateway; Azure Virtual WAN; Azure DNS; Azure CDN; Azure AD B2C=azure ad b2c; Entra External ID; Azure AD Connect=entra connect; Azure Information Protection; Azure Machine Learning Studio; Azure Cognitive Services=azure ai services; Azure OpenAI Service; Azure AI Search=cognitive search; Azure AI Foundry; Azure Bot Service; Azure Digital Twins; Azure IoT Hub=iot hub; Azure IoT Edge; Azure Sphere; Azure Maps; Azure Communication Services; Azure Virtual Desktop=avd; Windows 365; Azure Lab Services; Azure DevTest Labs; Azure Boards; Azure Repos; Azure Artifacts; Azure Test Plans; Azure Pipelines YAML; Azure Developer CLI=azd; Azure Functions Durable=durable functions; Azure Fundamentals=az-900; Azure Administrator Associate=az-104; Azure Developer Associate=az-204; Azure Solutions Architect=az-305; Azure DevOps Engineer Expert=az-400; Google Compute Engine=gce; Google Kubernetes Engine; Google Cloud Functions; Google Cloud Run; Google App Engine=gae; Google Cloud Storage=gcs bucket; Google Cloud SQL=cloud sql; Google Cloud Spanner=cloud spanner; Google Bigtable=cloud bigtable; Google Firestore; Google Memorystore; Google AlloyDB=alloydb; Google Pub/Sub Lite; Google Dataproc=dataproc; Google Dataprep; Google Data Fusion=cloud data fusion; Google Composer=cloud composer; Google Looker Studio Pro; Google Cloud Armor=cloud armor; Google Cloud CDN; Google Cloud Load Balancing; Google Cloud DNS; Google Cloud NAT; Google Cloud VPN; Google Cloud Interconnect; Google VPC Service Controls; Google Cloud IAM; Google Cloud KMS; Google Secret Manager; Google Security Command Center=scc; Google Chronicle SIEM; Google Cloud Build=cloud build; Google Artifact Registry; Google Container Registry=gcr; Google Cloud Deploy; Google Cloud Source Repositories; Google Cloud Logging=stackdriver; Google Cloud Monitoring; Google Cloud Trace; Google Cloud Profiler; Google Cloud Scheduler; Google Cloud Tasks; Google Workflows; Google Eventarc; Google Apigee; Google Anthos=anthos; Google Cloud Endpoints; Google Vertex AI Pipelines; Google Vertex AI Workbench; Google AutoML=automl; Google Vision AI; Google Natural Language API; Google Speech-to-Text; Google Dialogflow=dialogflow cx; Google Gemini API=gemini api; Google Document AI; Google Recommendations AI; Google TPU=cloud tpu; Google Colab=colaboratory; Google Cloud Shell; gcloud CLI=gcloud; Google Cloud SDK; Google Workspace=g suite; Google Apps Script=apps script; Google Cloud Digital Leader; Google Associate Cloud Engineer=gcp ace; Google Professional Cloud Architect; Google Professional Data Engineer; DigitalOcean Droplets=droplets; DigitalOcean Kubernetes=doks; DigitalOcean App Platform; Linode=akamai connected cloud; Vultr; Hetzner Cloud=hetzner; OVHcloud=ovh; Scaleway; UpCloud; Fly.io=flyio; Render.com=render cloud; Railway=railway.app; Koyeb; Northflank; Platform.sh; Aiven; CloudAMQP; Upstash; Neon=neon postgres; Turso; PlanetScale Vitess=vitess; Xata; Convex; Appwrite; PocketBase; Nhost; Back4App; Parse Server=parse platform; Kinvey; Backendless; Firebase Extensions; Tencent Cloud; Huawei Cloud; Yandex Cloud; Selectel; VK Cloud; SberCloud; Azercloud; Alibaba ECS; Alibaba OSS; Alibaba RDS; Alibaba ACK; Alibaba MaxCompute=maxcompute; Oracle Cloud Infrastructure; OCI Compute; OCI Object Storage; Oracle Autonomous Database=autonomous database; Oracle APEX=apex oracle; Oracle ADF; Oracle Forms; Oracle EBS=e-business suite; Oracle Fusion=oracle fusion; Oracle Siebel=siebel; Oracle PeopleSoft=peoplesoft; Oracle JD Edwards=jd edwards; Oracle Primavera; Oracle Hyperion; Oracle OBIEE=obiee; Oracle GoldenGate=goldengate; Oracle RAC=real application clusters; Oracle Data Guard=data guard; Oracle ASM; Oracle Exadata=exadata; Oracle WebLogic Server; Oracle SOA Suite=soa suite; Oracle Service Bus; Oracle Identity Manager; IBM Cloud Pak=cloud pak; IBM Db2=db2; IBM Informix=informix; IBM Cognos=cognos; IBM DataStage; IBM Watson=watsonx; IBM z/OS=z/os; IBM CICS=cics; IBM IMS; IBM AS/400=ibm i; IBM Power Systems; IBM Maximo=maximo; IBM Rational; IBM Netezza=netezza; IBM Sterling; IBM Tivoli=tivoli; IBM QRadar SIEM; IBM Guardium=guardium"""),
]
