// ====================================================
const gulp = require("gulp");
var { src, dest, parallel, watch, series } = require("gulp");
var sass = require("gulp-sass");
var browserSync = require("browser-sync").create();
const autoprefixer = require("gulp-autoprefixer");
// var concat = require('gulp-concat');
const concatCss = require("gulp-concat-css");
const debug = require("gulp-debug");
const cleanCss = require("gulp-clean-css");
const concat = require("gulp-concat");
// var replace1 = require('gulp-string-replace');
const ftp = require("gulp-ftp");
const cssunit = require("gulp-css-unit");
const sourcemaps = require("gulp-sourcemaps");
const gcmq = require("gulp-group-css-media-queries");
const smartgrid = require("smart-grid");

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
    notify: false,
    browser: [/*"chrome", */ "firefox"],
    tunnel: false
  });
}

function watchFiles() {
  watch("src/sass/**/*.sass", css);
  watch("src/*.html").on("change", browserSync.reload);
  watch("src/js/*.js").on("change", browserSync.reload);
  watch("src/css/*.css").on("change", browserSync.reload);
}

function css() {
  return (
    src("src/sass/**/*.sass")
      .pipe(sourcemaps.init())
      .pipe(debug({ title: "smaps_init" }))
      .pipe(sass().on("error", sass.logError))
      .pipe(debug({ title: "sass" }))
      // .on('error', console.error.bind(console))
      .pipe(concatCss("../css/style.css"))
      .pipe(debug({ title: "concatCss" }))
      .pipe(gcmq())
      .pipe(debug({ title: "gcmq" }))

      .pipe(
        autoprefixer({
          overrideBrowserslist: ["last 15 versions"],
          browsers: ["> 0.1%"],
          cascade: false
        })
      )
      .pipe(debug({ title: "autoprefixer" }))

      .pipe(
        cssunit({
          type: "px-to-vw",
          width: 1920
        })
      )
      .pipe(debug({ title: "cssunit" }))

      // .pipe(cleanCss({
      //     compatibility: 'ie8',
      //     level: 1,
      // }))
      // .pipe(debug({title: 'cleanCss'}))
      .pipe(sourcemaps.write())
      .pipe(debug({ title: "smaps_write" }))
      // .on('error', console.error.bind(console))
      .pipe(dest("src/css"))
      .pipe(browserSync.stream())
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
