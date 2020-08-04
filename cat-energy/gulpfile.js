// ====================================================
const gulp = require("gulp");
var { src, dest, parallel, watch, series } = require("gulp");
var sass = require("gulp-sass");
var browserSync = require("browser-sync").create();
const autoprefixer = require("gulp-autoprefixer");
const concatCss = require("gulp-concat-css");
const gcmq = require("gulp-group-css-media-queries");
const csso = require("gulp-csso");
const rename = require("gulp-rename");
const plumber = require("gulp-plumber");
// const cssunit = require("gulp-css-unit");
// const concat = require("gulp-concat");
// const cleanCss = require("gulp-clean-css");
// const debug = require("gulp-debug");
// const ftp = require("gulp-ftp");
// const sourcemaps = require("gulp-sourcemaps");
// const smartgrid = require("smart-grid");



// gulp.task('replace1', function() {
//     return gulp.src('src/css/style-tmp.css')
//         .pipe(debug())
//         .pipe(replace1('xxx', 'px'))
//         .pipe(debug())
//         .pipe(gulp.dest('src/css/style.css'));
// });

function browser() {
  browserSync.init({
    server: {
      baseDir: "./src"
    },
    logLevel: 'info',
    notify: false,
    // browser: ["chrome",  "firefox"],
    browser: "C:\\Program Files\\Firefox Developer Edition\\firefox.exe", 
    reloadDelay: 0, //1000
    tunnel: false
  });
}

function watchFiles() {
  watch("src/sass/**/*.sass", css);
  watch("src/*.html").on("change", browserSync.reload);
  watch("src/js/*.js").on("change", browserSync.reload);
  watch("src/css/*.css").on("change", browserSync.stream);
}

function css() {
  return (
    src("src/sass/**/*.sass")
      .pipe(plumber())
      // .pipe(sourcemaps.init())
      .pipe(sass().on("error", sass.logError))
      .pipe(concatCss("../css/style.css"))
      .pipe(gcmq())

      .pipe(
        autoprefixer({
          overrideBrowserslist: ["last 7 versions"],
          browsers: ["> 0.3%"],
          cascade: false
              })
            )

      // .pipe(
      //   cssunit({
      //     type: "px-to-vw",
      //     width: 1920
      //   })
      // )
      // .pipe(debug({ title: "cssunit" }))

      // .pipe(cleanCss({
      //     compatibility: 'ie8',
      //     level: 1,
      // }))
      // .pipe(sourcemaps.write())
      // 
      // 
      // .pipe(dest("src/css"))
      // .pipe(rename("style.min.css"))
      // .pipe(csso())
      .pipe(dest("src/css"))
      .pipe(browserSync.stream())
  );
}

function build() {
  return (
    src("src/sass/**/*.sass")
      .pipe(plumber())
      .pipe(sass().on("error", sass.logError))
      .pipe(concatCss("../css/style.css"))
      .pipe(gcmq())

      .pipe(
        autoprefixer({
          overrideBrowserslist: ["last 7 versions"],
          browsers: ["> 0.1%"],
          cascade: false
        })
      )

      .pipe(dest("build/css"))
      .pipe(rename("style.min.css"))
      .pipe(csso())
      .pipe(dest("build/css"))
  );
}


function grid(done) {
  let settings = {
    outputStyle: "sass",
    filename: "_smart-grid",
    columns: 24,
    offset: "0.52083vw",
    container: {
      maxWidth: "49.47917vw",
      fields: "1.5625vw"
    },
    breakPoints: {
      md: {
        width: "920px",
        fields: "15px"
      },
      sm: {
        width: "720px"
      },
      xs: {
        width: "576px"
      }
    }
  };
  smartgrid("./src/sass/", settings);
  done();
}

exports.css = css;

exports.default = series(series(css), parallel(browser, watchFiles));

gulp.task("grid", grid);
gulp.task("build", build);

/*gulp.task('default', function () {
    return gulp.src('src/**')
        .pipe(ftp({
            host: 'website.com',
            user: 'johndoe',
            pass: '1234',
            remotePath: '/public_html/emlab.fun/streams'
        }))
        .pipe(gutil.noop());
});*/

// gulp.task('scripts', ['clean-js'], function () {
//     return gulp.src(js.src)
//         .pipe(replace(/http:\/\/localhost:\d+/g, 'http://example.com'))
//         .pipe(uglify())
//         .pipe(concat('js.min.js'))
//         .pipe(gulp.dest('content/bundles/'))
//         .pipe(gzip(gzip_options))
//         .pipe(gulp.dest('content/bundles/'));
// });
